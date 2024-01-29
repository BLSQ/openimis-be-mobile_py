from django.db.models import Q

from graphene_django.filter import DjangoFilterConnectionField

# We do need all queries and mutations in the namespace here.
from .gql_queries import *  # lgtm [py/polluting-import]
from .gql_mutations import *  # lgtm [py/polluting-import]


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
