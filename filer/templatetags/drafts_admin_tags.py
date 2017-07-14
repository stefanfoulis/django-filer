# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django import template

register = template.Library()


@register.inclusion_tag('admin/filer/drafts/submit_line.html', takes_context=True)
def drafts_submit_row(context):
    """
    Displays the row of buttons for delete, save and draft/live logic.
    """
    is_readonly = context.get('is_readonly', False)
    # ---------- begin copied from django 1.8.18
    opts = context['opts']
    change = context['change']
    is_popup = context['is_popup']
    save_as = context['save_as']
    ctx = {
        'opts': opts,
        'show_delete_link': (
            not is_popup and context['has_delete_permission'] and
            change and context.get('show_delete', True)
        ),
        'show_save_as_new': not is_popup and change and save_as,
        'show_save_and_add_another': (
            context['has_add_permission'] and not is_popup and
            (not save_as or context['add'])
        ),
        'show_save_and_continue': not is_popup and context['has_change_permission'],
        'is_popup': is_popup,
        'show_save': True,
        'preserved_filters': context.get('preserved_filters'),
    }
    if context.get('original') is not None:
        ctx['original'] = context['original']
    # ---------- end copied from django
    obj = context.get('original')
    show_delete_link = ctx['show_delete_link']
    if is_readonly:
        for key in ctx.keys():
            if key.startswith('show_'):
                ctx[key] = False
    if obj:
        if show_delete_link and obj.is_draft and not obj.is_published:
            # Not published drafts can be deleted the usual way
            ctx['show_delete_link'] = True
        else:
            ctx['show_delete_link'] = False
        buttons = context.get('draft_workflow_buttons', {})
        ctx['draft_workflow_buttons'] = buttons

    return ctx
