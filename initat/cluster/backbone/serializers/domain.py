#!/usr/bin/python-init

from rest_framework import serializers
from initat.cluster.backbone.models import domain_tree_node, category, location_gfx, device_mon_location

__all__ = [
    "domain_tree_node_serializer",
    "category_serializer",
    "location_gfx_serializer",
    "device_mon_location_serializer",
]


class domain_tree_node_serializer(serializers.ModelSerializer):
    tree_info = serializers.Field(source="__unicode__")

    class Meta:
        model = domain_tree_node


class category_serializer(serializers.ModelSerializer):
    allow_add_remove = True
    num_refs = serializers.Field(source="get_references")

    class Meta:
        model = category


class location_gfx_serializer(serializers.ModelSerializer):
    icon_url = serializers.Field(source="get_icon_url")
    image_url = serializers.Field(source="get_image_url")

    class Meta:
        model = location_gfx


class device_mon_location_serializer(serializers.ModelSerializer):
    device_name = serializers.Field(source="get_device_name")

    class Meta:
        model = device_mon_location