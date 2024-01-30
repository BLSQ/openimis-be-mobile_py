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
from policy.gql_mutations import PolicyInputType
from policy.services import PolicyService
from mobile.apps import MobileConfig


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
        try:
            if type(user) is AnonymousUser or not user.id:
                raise ValidationError("mutation.authentication_required")
            if any(not user.has_perms(right) for right in MOBILE_ENROLLMENT_RIGHTS):
                raise PermissionDenied("unauthorized")

            with transaction.atomic():  # either everything succeeds, or everything fails
                from core.utils import TimeUtils
                now = TimeUtils.now()
                family_data = data["family"]
                insuree_data = data["insurees"]
                policy_data = data["policies"]
                premium_data = data["premiums"]

                # 1 - Creating/Updating the family with the head insuree
                logger.info(f"Creating/Updating the family with head insuree {family_data['head_insuree']['chf_id']}")
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
                    policy = PolicyService(user).update_or_create(current_policy_data, user)
                    policy_ids_mapping[mobile_id] = policy.uuid  # Storing the backend UUID

                # 4 - Creating/Updating premiums
                for current_premium_data in premium_data:
                    logger.info(f"Creating/Updating a premium for family {family.id} and policy {policy.id}")
                    add_audit_values(current_premium_data, user.id_for_audit, now)
                    mobile_policy_id = current_premium_data.pop("policy_id")
                    current_premium_data["policy_uuid"] = policy_ids_mapping[mobile_policy_id]
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


class Mutation(graphene.ObjectType):
    mobile_enrollment = MobileEnrollmentMutation.Field()
