import graphene
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db.models import Q

from contribution.gql_queries import PremiumGQLType
from core import ExtendedConnection
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from core.schema import OpenIMISMutation
from insuree.gql_mutations import FamilyBase, InsureeBase
from policy.gql_mutations import PolicyInputType
from .models import Control


class ControlGQLType(DjangoObjectType):
    class Meta:
        model = Control
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            'name': ['exact', 'icontains', 'istartswith'],
            'adjustability': ['exact', 'icontains', 'istartswith'],
            'usage': ['exact', 'icontains', 'istartswith'],
        }
        connection_class = ExtendedConnection


class PolicyEnrollmentGQLType(PolicyInputType):
    premiums = graphene.List(PremiumGQLType)


class FamilyEnrollmentGQLType(FamilyBase):
    insurees = graphene.List(InsureeBase)
    policies = graphene.List(PolicyEnrollmentGQLType)


class EnrollmentGQLType(OpenIMISMutation.Input):
    family_enrollment = graphene.Field(FamilyEnrollmentGQLType, required=True)


class MobileEnrollmentMutation(OpenIMISMutation):
    _mutation_module = "mobile"
    _mutation_class = "MobileEnrollmentMutation"

    class Input(EnrollmentGQLType, OpenIMISMutation.Input):
        pass

    @classmethod
    def async_mutate(cls, user, **data):
        try:
            if type(user) is AnonymousUser or not user.id:
                raise ValidationError("mutation.authentication_required")
            # TODO
            # if not user.has_perms(CoreConfig.gql_mutation_create_roles_perms):
            #     raise PermissionDenied("unauthorized")
            # if check_role_unique_name(data.get('name', None)):
            #     raise ValidationError("mutation.duplicate_of_role_name")
            from core.utils import TimeUtils
            data['validity_from'] = TimeUtils.now()
            data['audit_user_id'] = user.id_for_audit
            # TODO enrollment(data, user)
            return None
        except Exception as exc:
            return [
                {
                    'message': "core.mutation.failed_to_enroll",
                    'detail': str(exc)
                }]


class Mutation(graphene.ObjectType):
    enrollment = MobileEnrollmentMutation.Field()


class Query(graphene.ObjectType):
    control = DjangoFilterConnectionField(ControlGQLType)
    control_str = DjangoFilterConnectionField(
        ControlGQLType,
        str=graphene.String()
    )

    def resolve_control_str(self, info, **kwargs):
        search_str = kwargs.get('str')
        if search_str is not None:
            return Control.objects \
                .filter(
                Q(adjustability__icontains=search_str) | Q(name__icontains=search_str) | Q(usage__icontains=search_str))
        else:
            return Control.objects
