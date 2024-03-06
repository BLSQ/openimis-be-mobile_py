import logging

import graphene
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from graphene import InputObjectType

from contribution.gql_mutations import PremiumBase, update_or_create_premium

from core.schema import OpenIMISMutation
from insuree.gql_mutations import FamilyBase, InsureeBase
from insuree.services import FamilyService, InsureeService
from payer.models import Payer
from policy.gql_mutations import PolicyInputType, CreateRenewOrUpdatePolicyMutation
from policy.gql_queries import PolicyGQLType
from policy.models import Policy, PolicyRenewal
from policy.services import PolicyService, process_create_renew_or_update_policy
from mobile.apps import MobileConfig
from policy.values import policy_values


logger = logging.getLogger(__name__)


class PremiumEnrollmentGQLType(PremiumBase, InputObjectType):
    policy_id = graphene.Int(required=True)


class PolicyEnrollmentGQLType(PolicyInputType, InputObjectType):
    mobile_id = graphene.Int(required=True)


class InsureeEnrollmentGQLType(InsureeBase, InputObjectType):
    pass


class FamilyEnrollmentGQLType(FamilyBase, InputObjectType):
    pass


class MobileEnrollmentGQLType:
    family = graphene.Field(FamilyEnrollmentGQLType, required=True)
    insurees = graphene.List(InsureeEnrollmentGQLType)  # for families with more than the head insuree
    policies = graphene.List(PolicyEnrollmentGQLType, required=True)
    premiums = graphene.List(PremiumEnrollmentGQLType, required=True)


MOBILE_ENROLLMENT_RIGHTS = [
    MobileConfig.gql_mutation_create_families_perms,
    MobileConfig.gql_mutation_update_families_perms,
    MobileConfig.gql_mutation_create_insurees_perms,
    MobileConfig.gql_mutation_update_insurees_perms,
    MobileConfig.gql_mutation_create_policies_perms,
    MobileConfig.gql_mutation_edit_policies_perms,
    MobileConfig.gql_mutation_create_premiums_perms,
    MobileConfig.gql_mutation_update_premiums_perms,
]


class MobileEnrollmentMutation(OpenIMISMutation):
    _mutation_module = "mobile"
    _mutation_class = "MobileEnrollmentMutation"

    class Input(MobileEnrollmentGQLType, OpenIMISMutation.Input):
        pass

    @classmethod
    def async_mutate(cls, user, **data):
        logger.info("Receiving new mobile enrollment request")
        logger.info(data)
        try:
            if type(user) is AnonymousUser or not user.id:
                raise ValidationError("mutation.authentication_required")
            if any(not user.has_perms(right) for right in MOBILE_ENROLLMENT_RIGHTS):
                raise PermissionDenied("unauthorized")

            with transaction.atomic():  # either everything succeeds, or everything fails
                from core.utils import TimeUtils
                now = TimeUtils.now()
                # Cleaning up None values received from the mobile app
                cleaned_data = delete_none(data)
                family_data = cleaned_data["family"]
                insuree_data = cleaned_data["insurees"]
                policy_data = cleaned_data["policies"]
                premium_data = cleaned_data["premiums"]

                # 1 - Creating/Updating the family with the head insuree
                logger.info(f"Creating/Updating the family with head insuree {family_data['head_insuree']['chf_id']}")
                family_data.pop("id")
                add_audit_values(family_data, user.id_for_audit, now)
                family = FamilyService(user).create_or_update(family_data)

                # 2 - Creating/Updating the remaining insurees
                for insuree in insuree_data:
                    logger.info(f"Creating/Updating insuree {insuree['chf_id']}")
                    add_audit_values(insuree, user.id_for_audit, now)
                    insuree["family_id"] = family.id
                    InsureeService(user).create_or_update(insuree)

                # 3 - Creating/Updating policies
                policy_ids_mapping = {}  # storing the mobile internal IDs and their related backend UUIDs b/c premiums need UUIDs
                for current_policy_data in policy_data:
                    logger.info(f"Creating/Updating a policy for family {family.id}")
                    mobile_id = current_policy_data.pop("mobile_id")  # Removing the mobile internal ID
                    add_audit_values(current_policy_data, user.id_for_audit, now)
                    current_policy_data["family_id"] = family.id
                    
                    if "uuid" not in current_policy_data:
                        # It means it's a creation. These fields are added by the CreatePolicyMutation before calling the service
                        current_policy_data["status"] = Policy.STATUS_IDLE
                        current_policy_data["stage"] = Policy.STAGE_NEW

                    policy = PolicyService(user).update_or_create(current_policy_data, user)
                    policy_ids_mapping[mobile_id] = policy.uuid  # Storing the backend UUID

                # 4 - Creating/Updating premiums
                for current_premium_data in premium_data:
                    logger.info(f"Creating/Updating a premium for family {family.id} and policy {policy.id}")
                    add_audit_values(current_premium_data, user.id_for_audit, now)
                    mobile_policy_id = current_premium_data.pop("policy_id")
                    current_premium_data["policy_uuid"] = policy_ids_mapping[mobile_policy_id]
                    current_premium_data["is_offline"] = False
                    update_or_create_premium(current_premium_data, user)  # There is no PremiumService, so we're using directly the function in the gql_mutations file

                logger.info(f"Mobile enrollment processed successfully!")
                return None
        except Exception as exc:
            return [
                {
                    'message': "core.mutation.failed_to_enroll",
                    'detail': str(exc)
                }]


def add_audit_values(data: dict, user_id: int, now):
    data["validity_from"] = now
    data["audit_user_id"] = user_id


# Somehow, the library used for preparing GQL queries and sending data is not able to remove fields that have a null value
# Since the current GQL/Graphene/... version does not support null values, everything is built thinking we won't have null values, and here, we do
# It breaks things (imagine having a UUID=None) so we need to clean data before sending it to the various services
# Function taken from https://stackoverflow.com/a/66127889
def delete_none(_dict):
    for key, value in list(_dict.items()):
        if isinstance(value, dict):
            delete_none(value)
        elif value is None:
            del _dict[key]
        elif isinstance(value, list):
            for v_i in value:
                if isinstance(v_i, dict):
                    delete_none(v_i)
    return _dict


class MobilePolicyRenewalAndPremiumGQLType:
    renewal_id = graphene.Int(required=True)
    renewal_date = graphene.Date(required=True)
    officer_id = graphene.Int(required=True)
    receipt = graphene.String(required=True)
    pay_type = graphene.String(required=True, max_length=1)
    amount = graphene.Decimal(max_digits=18, decimal_places=2, required=True)
    payer_id = graphene.Int(required=False)

    # The fields under this comment are used when creating a new renewal from scratch from the mobile app
    # renewal_id = graphene.Int(required=False)
    # chf_id = graphene.String(required=False)
    # product_code = graphene.String(required=False)
    # product_id = graphene.String(required=False)


MOBILE_POLICY_RENEWAL_AND_PREMIUM_RIGHTS = [
    MobileConfig.gql_mutation_renew_policies_perms,
    MobileConfig.gql_mutation_create_premiums_perms,
]


class MobilePolicyRenewalAndPremium(CreateRenewOrUpdatePolicyMutation):
    _mutation_module = "mobile"
    _mutation_class = "MobilePolicyRenewalAndPremiumMutation"

    class Input(MobilePolicyRenewalAndPremiumGQLType, OpenIMISMutation.Input):
        pass

    @classmethod
    def async_mutate(cls, user, **data):
        logger.info("Receiving new mobile policy renewal & premium request")
        logger.info(data)
        try:
            with transaction.atomic():
                if type(user) is AnonymousUser or not user.id:
                    raise ValidationError("mutation.authentication_required")
                if any(not user.has_perms(right) for right in MOBILE_POLICY_RENEWAL_AND_PREMIUM_RIGHTS):
                    raise PermissionDenied("unauthorized")

                renewal_id = data["renewal_id"]
                policy_renewal = PolicyRenewal.objects.filter(validity_to__isnull=True, id=renewal_id).first()
                if not policy_renewal:
                    error_message = f"Error - unknown PolicyRenewal - ID={renewal_id}"
                    logger.error(error_message)
                    raise ValueError(error_message)

                logger.info(f"Processing policy renewal ID {renewal_id}")
                old_policy = policy_renewal.policy
                product = policy_renewal.new_product
                family = policy_renewal.insuree.family
                new_policy_start_date = policy_renewal.renewal_date
                renewal_received_amount = data["amount"]

                # 1st step is to reproduce the calls the FE web app does to fetch all the necessary data for creating the new policy
                policy_preparation_data = PolicyGQLType(
                    stage=Policy.STAGE_RENEWED,
                    enroll_date=new_policy_start_date,
                    start_date=new_policy_start_date,
                    product=product,
                )
                missing_policy_data, warnings = policy_values(policy_preparation_data, family, old_policy)

                # Doing some checks to make sure that the policy can be created
                if warnings and len(warnings):
                    logger.error("There were some warnings with the preparation of the new policy")
                    return warnings
                renewed_policy_value = missing_policy_data.value
                if renewal_received_amount < renewed_policy_value:
                    error_message = (f"Error - payment is too low to renew policy - "
                                     f"required amount={renewed_policy_value}, "
                                     f"received amount={renewal_received_amount}")
                    logger.error(error_message)
                    raise ValueError(error_message)
                elif renewal_received_amount == renewed_policy_value:
                    logger.info("The required amount matches the received amount")
                else:
                    logger.info("The received amount is higher than the required amount")

                renewed_policy_data = {
                    "status": Policy.STATUS_IDLE,
                    "stage": Policy.STAGE_RENEWED,
                    "enroll_date": data["renewal_date"],
                    "start_date": missing_policy_data.start_date,
                    "expiry_date": missing_policy_data.expiry_date,
                    "value": renewed_policy_value,
                    "product_id": product.id,
                    "family_id": family.id,
                    "officer_id": user.officer_id,
                }
                renewed_policy, errors = process_create_renew_or_update_policy(user, renewed_policy_data)
                if errors and len(errors):
                    logger.error("There were some error with the new policy")
                    return errors

                # Now that the new policy was created, the premium can be created too
                payer = None
                if "payer_id" in data:
                    payer = Payer.objects.filter(id=data["payer_id"]).first()

                premium_data = {
                    "policy_uuid": renewed_policy.uuid,
                    "amount": renewal_received_amount,
                    "payer_uuid": payer.uuid if payer else None,
                    "receipt": data["receipt"],
                    "pay_date": data["renewal_date"],
                    "pay_type": data["pay_type"],
                    "is_photo_fee": False,
                }
                update_or_create_premium(premium_data, user)

                return None
        except Exception as exc:
            return [
                {
                    'message': "core.mutation.failed_to_enroll",
                    'detail': str(exc)
                }]


class Mutation(graphene.ObjectType):
    mobile_enrollment = MobileEnrollmentMutation.Field()
    mobile_policy_renewal_and_premium = MobilePolicyRenewalAndPremium.Field()
