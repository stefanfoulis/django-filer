# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import OrderedDict

from copy import copy
from django.core.urlresolvers import reverse


class DraftLiveAdminMixin(object):
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super(DraftLiveAdminMixin, self).get_readonly_fields(request, obj=obj)
        if not obj:
            return readonly_fields
        if obj.is_live:
            readonly_fields = set(readonly_fields)
            all_field_names = set(obj._meta.get_all_field_names())
            readonly_fields = readonly_fields | all_field_names
        return list(readonly_fields)

    def get_detail_or_changelis_url(self, obj):
        if not obj or obj and not obj.pk:  # No pk means the object was deleted
            return self.get_admin_changelist_url(obj)
        else:
            return self.get_detail_admin_url(obj)

    def get_detail_admin_url(self, obj):
        info = obj._meta.app_label, obj._meta.model_name
        return reverse('admin:{}_{}_change'.format(*info), args=(obj.pk,))

    def get_admin_changelist_url(self, obj=None):
        info = obj._meta.app_label, obj._meta.model_name
        return reverse('admin:{}_{}_changelist'.format(*info))

    def draft_live_info(self, obj):
        if obj.deletion_requested:
            return '<div style="background-color: red; color: white; padding: 3px; text-align: center;">DELETION REQUESTED !!!</div>'
        if obj.is_live and obj.has_pending_changes:
            html = 'View Pending Changes: <a href="{}">draft</a>'.format(
                self.get_detail_admin_url(obj.draft),
            )
        elif obj.is_live:
            html = 'no pending changes'
        else:  # It is a draft
            try:
                if not obj.live_id:
                    raise AttributeError
                html = '<a href="{}">live</a>'.format(
                    self.get_detail_admin_url(obj.live),
                )
            except (obj._meta.model.DoesNotExist, AttributeError):
                html = 'no live version yet'
        return html
    draft_live_info.allow_tags = True
    draft_live_info.short_description = 'Publication status'

    def draft_or_live(self, obj):
        if obj.is_draft:
            return '<div style="background-color: blue; color: white; padding: 3px; text-align: center;">draft</div>'
        else:
            return '<div style="background-color: green; color: white; padding: 3px; text-align: center;">live</div>'
    draft_or_live.allow_tags = True
    draft_or_live.short_description = 'type'
    draft_or_live.admin_ordering = 'is_live'

    def get_buttons(self, request, obj):
        defaults = OrderedDict()
        defaults['create_draft'] = {'label': 'Create and edit draft'}
        defaults['edit_draft'] = {'label': 'Edit draft'}
        defaults['show_live'] = {'label': 'Show live version'}
        defaults['discard_draft'] = {'label': 'Discard draft'}
        defaults['publish'] = {'label': 'Publish', 'class': 'default'}
        defaults['request_deletion'] = {'label': 'Request deletion'}
        defaults['discard_requested_deletion'] = {'label': 'Discard requested deletion'}
        defaults['publish_deletion'] = {'label': 'Publish deletion', 'class': 'danger'}
        buttons = OrderedDict()
        for action in obj.available_actions(request.user).values():
            action_name = action['name']
            buttons[action_name] = copy(defaults[action_name])
            buttons[action_name].update(action)
            buttons[action_name]['field_name'] = '_{}'.format(action_name)

        # Additional links
        if obj.is_live and obj.has_pending_changes:
            # Add a link for editing an existing draft
            action_name = 'edit_draft'
            buttons[action_name] = copy(defaults[action_name])
            buttons[action_name]['url'] = self.get_detail_admin_url(obj.draft)
            buttons[action_name]['has_permission'] = True
        if obj.is_draft and obj.is_published:
            # Add a link to go back to live
            action_name = 'show_live'
            buttons[action_name] = copy(defaults[action_name])
            buttons[action_name]['url'] = self.get_detail_admin_url(obj.live)
            buttons[action_name]['has_permission'] = True
        return buttons
