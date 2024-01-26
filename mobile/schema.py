import graphene
from django.db.models import Q

from core import ExtendedConnection
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
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
                .filter(Q(adjustability__icontains=search_str) | Q(name__icontains=search_str) | Q(usage__icontains=search_str))
        else:
            return Control.objects
