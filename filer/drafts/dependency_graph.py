# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import itertools
from django.db.models.deletion import get_candidate_relations_to_delete


def get_related_objects(obj, excludes=None, using='default'):
    """
    Given a model instance will find all fields that have a ForeignKey,
    OneToOne or ManyToMany relationship to it.
    Returns a generator that yields all related model instances.
    """
    querysets = []
    for related_field in get_related_fields(obj._meta.model):
        querysets.append(
            related_field.field.model.objects.filter(
                **{related_field.field.name: obj}
            )
        )
    return itertools.chain(*[queryset.iterator() for queryset in querysets])


def update_relations(obj, new_obj):
    """
    Given an obj and a new_obj (must be the same model) will change all
    relationships pointing to obj to point to new_obj.
    """
    # TODO: If there is are relations to obj that are linking to both the live
    #       and draft versions this may cause an error at db levels because of
    #       unique constraints.
    # DONE: [WORKS!] Check if this works with ManyToMany
    # TODO: Check if this works with GenericForeignKeys
    # DONE: [WORKS!] Check if this works with OneToOne
    # TODO: Check if this work withs django-parler translated models
    # TODO: Check if this work withs django-hvad translated models
    # Mindbender: One of the related_fields will be the field that points from
    # the draft version to the live version. But since we filter the qs it does
    # not matter. It would only be a problem if we'd have a draft that points to
    # itself as live.
    count = 0
    for related_field in get_related_fields(obj._meta.model):
        queryset = related_field.field.model.objects
        update = {related_field.field.name: new_obj}
        count += (
            queryset
            .filter(**{related_field.field.name: obj})
            .update(**update)
        )
    return count


def get_related_fields(model):
    # Get a list of all fields from all models that point to this model.
    # get_candidate_relations_to_delete() correctly excludes the parent_link
    # relations from models with multi-table inheritance as long as they are
    # correctly defined (with the parent_link=True parameter if the
    # OneToOne for the link is manually defined).
    return get_candidate_relations_to_delete(model._meta)
