# -*- coding: utf-8 -*-
import six

from lxml import etree
from lxml.etree import Element, SubElement
from lxml.builder import E
from Products.ERP5Type.Utils import str2unicode, bytes2str

def formToXML(form, prologue=1):
    """Takes a formulator form and serializes it to an XML representation.
    """
    form_as_xml = Element('form')
    encoding = form.stored_encoding or 'utf-8'
    # export form settings
    for field in form.settings_form.get_fields(include_disabled=1):
      id = field.id
      value = getattr(form, id)
      if id == 'unicode_mode':
        if value:
          value = 'true'
        else:
          value = 'false'
      sub_element = SubElement(form_as_xml, id)
      sub_element.text = str2unicode(str(value), encoding)
    groups = SubElement(form_as_xml, 'groups')
    # export form groups
    for group in form.get_groups(include_empty=1):
      group_element = SubElement(groups, 'group')
      group_element.append(E.title(str2unicode(group, encoding)))

      fields = SubElement(group_element, 'fields')
      for field in form.get_fields_in_group(group, include_disabled=1):
        field_element = E.field(
                                  E.id(str(field.id)),
                                  E.type(str(field.meta_type))
                               )

        fields.append(field_element)
        values_element = SubElement(field_element, 'values')
        items = sorted(field.values.items())
        for key, value in items:
          if value is None:
            continue
          if value is True: # XXX Patch
            value = 1 # XXX Patch
          if value is False: # XXX Patch
            value = 0 # XXX Patch
          if callable(value): # XXX Patch
            value_element = SubElement(values_element, key, type='method')
          elif isinstance(value, float):
            value_element = SubElement(values_element, key, type='float')
          elif isinstance(value, int):
            value_element = SubElement(values_element, key, type='int')
          elif isinstance(value, list):
            value_element = SubElement(values_element, key, type='list')
          else:
            if not isinstance(value, six.string_types):
              value = str(value)
            value_element = SubElement(values_element, key)
          value_element.text = str2unicode(str(value), encoding)

        tales_element = SubElement(field_element, 'tales')
        items = sorted(field.tales.items())
        for key, value in items:
          if value:
            tale_element = SubElement(tales_element, key)
            tale_element.text = str2unicode(str(value._text), encoding)

        messages = SubElement(field_element, 'messages')
        for message_key in field.get_error_names():
          message_element = SubElement(messages, 'message', name=message_key)
          message_element.text = str2unicode(field.get_error_message(message_key), encoding)
        # Special attribute for ProxyFields *delegated_list*
        delegated_list = getattr(field, 'delegated_list', [])
        if delegated_list:
          delegated_list_element = SubElement(field_element, 'delegated_list')
          delegated_list.sort()
          [SubElement(delegated_list_element, delegated) for delegated in delegated_list]

    encoding = 'utf-8' if form.unicode_mode else form.stored_encoding
    xml = etree.tostring(
      form_as_xml,
      encoding=encoding,
      xml_declaration=True,
      pretty_print=True,
    )
    return bytes2str(xml, encoding=encoding)
