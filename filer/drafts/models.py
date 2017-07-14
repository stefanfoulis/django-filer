# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.functional import cached_property


class DraftLiveQuerySetMixin(object):
    def live(self):
        return self.filter(is_live=True)

    def draft(self):
        return self.filter(is_live=False)

    def pending_deletion(self):
        return self.filter(is_live=True, deletion_requested=True)

    def pending_changes(self):
        return self.filter(
            Q(is_live=False) |
            Q(is_live=True, draft__isnull=False)
        )


class DraftLiveQuerySet(DraftLiveQuerySetMixin, models.QuerySet):
    pass


class DraftLiveMixin(models.Model):
    ignore_copy_fields = (
        'pk',
        'id',
        'is_live',
        'live',
        'draft',
        'published_at',
        'deletion_requested',
        # FIXME: filer specific (multi table inheritance)
        'file_ptr',
    )
    is_live = models.BooleanField(
        default=False,
        editable=False,
    )
    live = models.OneToOneField(
        to='self',
        blank=True,
        null=True,
        default=None,
        related_name='draft',
        limit_choices_to={'live_id__isnull': True},
        editable=False,
    )
    published_at = models.DateTimeField(
        blank=True,
        null=True,
        default=None,
        editable=False,
    )
    deletion_requested = models.BooleanField(
        default=False,
        editable=False,
    )

    objects = DraftLiveQuerySet.as_manager()

    class Meta:
        abstract = True

    # USER OVERRIDABLE METHODS
    def copy_relations(self, old_obj):
        pass

    def copy_object(self, old_obj, commit=True):
        # TODO: use the id swapping trick (but remember to set live_id too!)
        for field in self._meta.get_fields():
            if not field.concrete or field.name in self.ignore_copy_fields:
                continue
            setattr(self, field.name, getattr(old_obj, field.name))
        if commit:
            self.save()
            self.copy_relations(old_obj=old_obj)

    def can_publish(self):
        assert self.is_draft
        # FOR SUBCLASSES
        # Checks whether the data and all linked data is ready to publish.
        # Raise ValidationError if not.

    def user_can_publish(self, user):
        # FOR SUBCLASSES
        # Checks whether the user has permissions to publish
        return True
    # END USER OVERRIDABLE METHODS

    def clean(self):
        super(DraftLiveMixin, self).clean()
        if self.is_live and self.live_id:
            raise ValidationError(
                'A live object can\'t set the live relationship.'
            )
        if self.is_draft and self.deletion_requested:
            raise ValidationError('invalid')

    @property
    def is_draft(self):
        return not self.is_live

    @property
    def is_published(self):
        if self.is_live:
            return True
        else:
            return bool(self.live_id)

    @cached_property
    def has_pending_changes(self):
        if self.is_draft:
            return True
        else:
            try:
                # Query! Can probably be avoided by using
                # .select_related('draft') in the queryset.
                return bool(self.draft)
            except ObjectDoesNotExist:
                return False

    @property
    def has_pending_deletion_request(self):
        return self.is_live and self.deletion_requested

    @transaction.atomic
    def create_draft(self):
        assert self.is_live
        if self.has_pending_deletion_request:
            self.discard_requested_deletion()
        # TODO: Get draft without a query (copy in memory)
        # FIXME: use the same logic as publishing.
        draft = self._meta.model.objects.get(id=self.id)
        draft.pk = None
        draft.id = None
        draft.is_live = False
        draft.live = self
        draft.save()  # If this was called even though a draft already exists,
                      # we'll get the db error here.
        draft.copy_relations(old_obj=self)
        return draft

    @transaction.atomic
    def discard_draft(self):
        assert self.is_draft
        self.delete()

    @transaction.atomic
    def publish(self, validate=True):
        assert self.is_draft
        if validate:
            self.can_publish()
        now = timezone.now()
        existing_live = self.live
        if not existing_live:
            # This means there is no existing live version. So we can just make
            # this draft the live version. As a nice side-effect all existing
            # ForeignKeys pointing to this object will now be automatically
            # pointing the the live version. Win-win.
            self.is_live = True
            self.published_at = now
            self.save()
            return self

        # There is an existing live version:
        # * update the live version with the data from the draft
        # TODO: For some reason I am getting a unique constraint error even when
        #       saveing with force_update=True. Fallback to iterating over the
        #       fields.  ====> it is because we forgot to set live.draft=None
        # live = Thing.objects.get(pk=self.pk)
        # live.pk = existing_live.pk
        # live.published_at = now
        # live.is_live = True
        # live.save(force_update=True)
        live = self.live
        live.published_at = now
        live.copy_object(old_obj=self)
        # * find any other objects still pointing to the draft version and
        #   switch them to the live version. (otherwise cascade or set null will
        #   yield unexpected results)
        # fields = Thing._meta.get_fields()
        # # import ipdb; ipdb.set_trace()
        # for field in fields:
        #     # update
        #     print field
        # * Delete myself (draft)
        self.delete()
        return live

    @transaction.atomic
    def request_deletion(self):
        assert self.is_draft and self.is_published or self.is_live
        # shortcut to be able to request_deletion on a draft. Preferrably this
        # should be done on the live object.
        if self.is_draft:
            return self.live.request_deletion()

        # It is a live object
        if self.has_pending_changes:
            live = self.live
            draft = live.draft
        else:
            live = self
            draft = None

        live.deletion_requested = True
        live.save(update_fields=['deletion_requested'])
        if draft:
            draft.delete()
        return live

    @transaction.atomic
    def discard_requested_deletion(self):
        assert self.is_live
        self.deletion_requested = False
        self.save(update_fields=['deletion_requested'])

    @transaction.atomic
    def publish_deletion(self):
        assert self.has_pending_deletion_request
        self.delete()
        self.id = None
        return self

    def get_live(self):
        if self.is_live:
            return self
        if self.live_id:
            return self.live
        return None

    def available_actions(self, user):
        # TODO: include permission information
        actions = set()
        if self.deletion_requested:
            actions.add('discard_requested_deletion')
            actions.add('publish_deletion')
        if self.is_draft and self.has_pending_changes:
            actions.add('publish')
        if self.is_draft and self.has_pending_changes and self.is_published:
            actions.add('discard_draft')
        if self.is_live and not self.has_pending_changes:
            actions.add('create_draft')
        if self.is_live and not self.deletion_requested:
            actions.add('request_deletion')
        return sorted(list(actions))
