# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django import forms
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _

from .. import settings
from ..models import File
from ..utils.compatibility import LTE_DJANGO_1_5, LTE_DJANGO_1_6, unquote
from .permissions import PrimitivePermissionAwareModelAdmin
from .tools import AdminContext, admin_url_params_encoded, popup_status
from ..drafts.admin import DraftLiveAdminMixin


class FileAdminChangeFrom(forms.ModelForm):
    class Meta(object):
        model = File
        exclude = ()


class FileAdmin(DraftLiveAdminMixin, PrimitivePermissionAwareModelAdmin):
    list_display = ('label',)
    list_per_page = 10
    search_fields = ['name', 'original_filename', 'sha1', 'description']
    raw_id_fields = ('owner',)
    readonly_fields = (
        'sha1',
        'display_canonical',
        'draft_live_info',
        'draft_or_live',
    )
    save_on_top = True

    form = FileAdminChangeFrom

    def get_queryset(self, request):
        if LTE_DJANGO_1_5:
            return super(FileAdmin, self).queryset(request)
        return super(FileAdmin, self).get_queryset(request)

    @classmethod
    def build_fieldsets(cls, extra_main_fields=(), extra_advanced_fields=(),
                        extra_fieldsets=()):
        fieldsets = (
            (None, {
                'fields': (
                    ('draft_or_live', 'draft_live_info'),
                    'name',
                    'owner',
                    'description',
                ) + extra_main_fields,
            }),
            (_('Advanced'), {
                'fields': (
                    'file',
                    'sha1',
                    'display_canonical',
                ) + extra_advanced_fields,
                'classes': ('collapse',),
            }),
        ) + extra_fieldsets
        if settings.FILER_ENABLE_PERMISSIONS:
            fieldsets = fieldsets + (
                (None, {
                    'fields': ('is_public',)
                }),
            )
        return fieldsets

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = {} if extra_context is None else extra_context
        # Double query. Sad.
        obj = self.get_object(request, unquote(object_id))
        if obj.is_live:
            extra_context['is_readonly'] = True
            if obj.has_pending_changes:
                extra_context['admin_draft_change_url'] = self.get_detail_admin_url(obj.draft)
        extra_context['draft_workflow_buttons'] = self.get_buttons(request, obj)
        return self.changeform_view(request, object_id, form_url, extra_context)

    def get_admin_changelist_url(self, obj=None):
        return self.get_admin_directory_listing_url_for_obj(obj)

    def get_admin_directory_listing_url_for_obj(self, obj):
        if obj.folder_id:
            return reverse('admin:filer-directory_listing',
                      kwargs={'folder_id': obj.folder_id})
        else:
            return reverse(
                'admin:filer-directory_listing-unfiled_images')

    def response_change(self, request, obj):
        """
        Overrides the default to be able to forward to the directory listing
        instead of the default change_list_view and handles the draft/live
        related actions.
        """
        if request.POST and '_create_draft' in request.POST:
            draft = obj.create_draft()
            return HttpResponseRedirect(self.get_detail_admin_url(draft))
        elif request.POST and '_discard_draft' in request.POST:
            live = obj.get_live()
            obj.discard_draft()
            return HttpResponseRedirect(self.get_detail_or_changelis_url(live))
        elif request.POST and '_publish' in request.POST:
            live = obj.publish()
            return HttpResponseRedirect(self.get_detail_admin_url(live))
        elif request.POST and '_request_deletion' in request.POST:
            live = obj.request_deletion()
            return HttpResponseRedirect(self.get_detail_admin_url(live))
        elif request.POST and '_discard_requested_deletion' in request.POST:
            obj.discard_requested_deletion()
            return HttpResponseRedirect(self.get_detail_admin_url(obj))
        elif request.POST and '_publish_deletion' in request.POST:
            obj.publish_deletion()
            return HttpResponseRedirect(self.get_admin_changelist_url(obj))
        elif (
            request.POST and
            '_continue' not in request.POST and
            '_saveasnew' not in request.POST and
            '_addanother' not in request.POST
        ):
            # Popup in pick mode or normal mode. In both cases we want to go
            # back to the folder list view after save. And not the useless file
            # list view.
            url = self.get_admin_directory_listing_url_for_obj(obj)
            url = "{0}{1}".format(
                url,
                admin_url_params_encoded(request),
            )
            return HttpResponseRedirect(url)

        return super(FileAdmin, self).response_change(request, obj)

    def render_change_form(self, request, context, add=False, change=False,
                           form_url='', obj=None):
        info = self.model._meta.app_label, self.model._meta.model_name
        extra_context = {
            'history_url': 'admin:%s_%s_history' % info,
            'is_popup': popup_status(request),
            'filer_admin_context': AdminContext(request),
        }
        context.update(extra_context)
        return super(FileAdmin, self).render_change_form(
            request=request, context=context, add=add, change=change,
            form_url=form_url, obj=obj)

    def delete_view(self, request, object_id, extra_context=None):
        """
        Overrides the default to enable redirecting to the directory view after
        deletion of a image.

        we need to fetch the object and find out who the parent is
        before super, because super will delete the object and make it
        impossible to find out the parent folder to redirect to.
        """
        try:
            obj = self.get_queryset(request).get(pk=unquote(object_id))
            parent_folder = obj.folder
        except self.model.DoesNotExist:
            parent_folder = None

        admin_context = AdminContext(request)
        if LTE_DJANGO_1_6:
            extra_context = extra_context or {}
            extra_context.update({'is_popup': admin_context.popup})
        if request.POST:
            # Return to folder listing, since there is no usable file listing.
            super(FileAdmin, self).delete_view(
                request=request, object_id=object_id,
                extra_context=extra_context)
            if parent_folder:
                url = reverse('admin:filer-directory_listing',
                              kwargs={'folder_id': parent_folder.id})
            else:
                url = reverse('admin:filer-directory_listing-unfiled_images')
            url = "{0}{1}".format(
                url,
                admin_url_params_encoded(request)
            )
            return HttpResponseRedirect(url)

        return super(FileAdmin, self).delete_view(
            request=request, object_id=object_id,
            extra_context=extra_context)

    def get_model_perms(self, request):
        """
        These permissions are only used in the admin index view, causing
        Files to not appear in the global list. We allow navigating to it
        through the directory listing instead.
        """
        return {
            'add': False,
            'change': False,
            'delete': False,
        }

    def display_canonical(self, instance):
        canonical = instance.canonical_url
        if canonical:
            return '<a href="%s">%s</a>' % (canonical, canonical)
        else:
            return '-'
    display_canonical.allow_tags = True
    display_canonical.short_description = _('canonical URL')

FileAdmin.fieldsets = FileAdmin.build_fieldsets()
