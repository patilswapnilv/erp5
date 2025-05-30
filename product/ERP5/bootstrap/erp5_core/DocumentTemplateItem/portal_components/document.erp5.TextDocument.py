# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2002 Nexedi SARL and Contributors. All Rights Reserved.
#                    Jean-Paul Smets-Solanes <jp@nexedi.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

from hashlib import md5
import six
from AccessControl.ZopeGuards import guarded_getattr
from AccessControl import ClassSecurityInfo
from zLOG import LOG, WARNING
from Products.ERP5Type import Permissions, PropertySheet
from erp5.component.document.Document import Document, ConversionError, _MARKER, DEFAULT_CONTENT_TYPE
from erp5.component.document.File import File
from erp5.component.module.WebDAVSupport import TextContent
from erp5.component.document.Document import VALID_IMAGE_FORMAT_LIST, VALID_TEXT_FORMAT_LIST
from io import BytesIO
from string import Template

# Mixin Import
from erp5.component.mixin.CachedConvertableMixin import CachedConvertableMixin
from erp5.component.mixin.BaseConvertableFileMixin import BaseConvertableFileMixin
from Products.ERP5Type.mixin.text_content_history import TextContentHistoryMixin
from Products.ERP5Type.Utils import guessEncodingFromText, bytes2str, str2bytes, str2unicode, unicode2str

from lxml import html as etree_html
from lxml import etree

class TextDocument(CachedConvertableMixin, BaseConvertableFileMixin, TextContentHistoryMixin,
                                                            TextContent, File):
  """A TextDocument impletents IDocument, IFile, IBaseConvertable, ICachedconvertable
  and ITextConvertable
  """

  meta_type = 'ERP5 Text Document'
  portal_type = 'Text Document'
  add_permission = Permissions.AddPortalContent

  # Declarative security
  security = ClassSecurityInfo()
  security.declareObjectProtected(Permissions.AccessContentsInformation)

  # Declarative properties
  property_sheets = ( PropertySheet.Base
                    , PropertySheet.XMLObject
                    , PropertySheet.CategoryCore
                    , PropertySheet.DublinCore
                    , PropertySheet.Version
                    , PropertySheet.Document
                    , PropertySheet.ExternalDocument
                    , PropertySheet.Url
                    , PropertySheet.TextDocument
                    , PropertySheet.Data
                    , PropertySheet.Reference
                    )

  def _substituteTextContent(self, text, safe_substitute=True, **kw):
    # If a method for string substitutions of the text content, perform it.
    # Decode everything into unicode before the substitutions, in order to
    # avoid encoding errors.
    method_id = self.getTextContentSubstitutionMappingMethodId()
    if method_id:
      try:
        method = guarded_getattr(self, method_id)
      except AttributeError:
        LOG('TextDocument', WARNING, 'could not get the substitution'
            ' mapping method %s from %r, so the content will not be'
            ' substituted.' % (method_id, self.getRelativeUrl()))
        return text

      # unicode()
      is_str = isinstance(text, str)
      if six.PY2 and is_str:
        text = str2unicode(text)

      class LazyUnicodeMapping:
        """Lazily calls the substitution method if some substitution is needed
        and manage the str/unicode on py2.
        """
        _mapping = None
        @property
        def mapping(self):
          if self._mapping is None:
            self._mapping = method(**kw)
          return self._mapping

        def __getitem__(self, item):
          v = self.mapping[item]
          if six.PY2:
            if isinstance(v, str):
              v = str2unicode(v)
            elif not isinstance(v, six.text_type):
              v = str2unicode(str(v))
          else:
            if not isinstance(v, str):
              v = str(v)
          return v
      unicode_mapping = LazyUnicodeMapping()

      if safe_substitute:
        text = Template(text).safe_substitute(unicode_mapping)
      else:
        text = Template(text).substitute(unicode_mapping)

      # If the original was a str, convert it back from unicode() to str
      if six.PY2 and is_str:
        text = unicode2str(text)

    return text

  security.declareProtected(Permissions.AccessContentsInformation, 'asSubjectText')
  def asSubjectText(self, substitution_method_parameter_dict=None, safe_substitute=True, **kw):
    """
      Converts the subject of the document to a textual representation.
    """
    subject = TextDocument.inheritedAttribute('asSubjectText')(self, **kw)
    if substitution_method_parameter_dict is None:
      substitution_method_parameter_dict = {}
    return self._substituteTextContent(subject, safe_substitute=safe_substitute,
                                       **substitution_method_parameter_dict)

  def _convert(self, format, substitution_method_parameter_dict=None, # pylint: disable=redefined-builtin
              safe_substitute=True, charset=None, text_content=None, substitute=True, **kw):
    """
      Convert text using portal_transforms or oood
    """
    # XXX 'or DEFAULT_CONTENT_TYPE' is compaptibility code used for old
    # web_page that have neither content_type nor text_format. Migration
    # should be done to make all web page having content_type property
    src_mimetype = self.getContentType() or DEFAULT_CONTENT_TYPE
    if not format and src_mimetype == 'text/html':
      format = 'html' # Force safe_html
    if not format:
      # can return document without conversion
      return src_mimetype, self.getTextContent()
    portal = self.getPortalObject()
    mime_type = portal.mimetypes_registry.lookupExtension('name.%s' % format)
    original_mime_type = mime_type = str(mime_type)
    if text_content is None:
      # check if document has set text_content and convert if necessary
      text_content = self.getTextContent()
    if text_content:
      kw['format'] = format
      convert_kw = {}
      # PortalTransforms does not accept empty values for 'encoding' parameter
      if charset:
        kw['charset'] = convert_kw['encoding'] = charset
      if not self.hasConversion(**kw):
        portal_transforms = portal.portal_transforms
        filename = self.getFilename()
        if mime_type == 'text/html':
          mime_type = 'text/x-html-safe'
        if src_mimetype != "image/svg+xml":
          data = text_content
          if not isinstance(data, bytes):
            data = str2bytes(data)
          result = portal_transforms.convertToData(mime_type, data,
                                                   object=self, context=self,
                                                   filename=filename,
                                                   mimetype=src_mimetype,
                                                   **convert_kw)
          if result is None:
            raise ConversionError('TextDocument conversion error. '
                                  'portal_transforms failed to convert '
                                  'from %r to %s: %r' %
                                  (src_mimetype, mime_type, self))
        else:
          result = text_content
        if format in VALID_IMAGE_FORMAT_LIST:
          # Include extra parameter for image conversions
          temp_image = self.portal_contributions.newContent(
                                       portal_type='Image',
                                       file=BytesIO(),
                                       filename=self.getId(),
                                       temp_object=1)
          if not isinstance(result, bytes):
            result = str2bytes(result)
          temp_image._setData(result)
          _, result = temp_image.convert(**kw)

        self.setConversion(result, original_mime_type, **kw)
      else:
        mime_type, result = self.getConversion(**kw)
      if format in VALID_TEXT_FORMAT_LIST:
        if six.PY3 and isinstance(result, bytes):
          result = bytes2str(result)
        if substitute:
          # only textual content can be sustituted
          if substitution_method_parameter_dict is None:
            substitution_method_parameter_dict = {}
          result = self._substituteTextContent(result, safe_substitute=safe_substitute,
                                               **substitution_method_parameter_dict)
      return original_mime_type, result
    else:
      # text_content is not set, return empty string instead of None
      return original_mime_type, ''

  security.declareProtected(Permissions.AccessContentsInformation, 'getContentBaseURL')
  def getContentBaseURL(self):
    """
        Returns the content base URL based on the actual content
        (in HTML)
    """
    if self.hasTextContent():
      html = self._asHTML()
      # a document can be entirely stripped by safe_html
      # so its html conversion can be empty
      if html.strip():
        html_tree = etree_html.fromstring(html)
        base_list = [href for href in html_tree.xpath('//base/@href') if href]
        if base_list:
          return str(base_list[0])
    return Document.getContentBaseURL(self)

  security.declareProtected(Permissions.ModifyPortalContent, 'setBaseData')
  def setBaseData(self, value):
    """Store base_data into text_content
    """
    self._setTextContent(bytes2str(value))

  security.declareProtected(Permissions.ModifyPortalContent, '_setBaseData')
  _setBaseData = setBaseData

  security.declareProtected(Permissions.ModifyPortalContent, '_baseSetBaseData')
  _baseSetBaseData = _setBaseData

  security.declareProtected(Permissions.ModifyPortalContent, 'setBaseContentType')
  def setBaseContentType(self, value):
    """store value into content_type
    """
    self._setContentType(value)

  security.declareProtected(Permissions.ModifyPortalContent, '_setBaseContentType')
  _setBaseContentType = setBaseContentType

  security.declareProtected(Permissions.ModifyPortalContent, '_baseSetBaseContentType')
  _baseSetBaseContentType = _setBaseContentType

  security.declareProtected(Permissions.AccessContentsInformation, 'getBaseData')
  def getBaseData(self, default=_MARKER):
    """
    """
    self._checkConversionFormatPermission(None)
    if default is _MARKER:
      text_content = self.getTextContent()
    else:
      text_content = self.getTextContent(default=default)
    if six.PY3 and text_content and text_content is not default:
      text_content = str2bytes(text_content)
    return text_content

  security.declareProtected(Permissions.AccessContentsInformation, 'hasBaseData')
  def hasBaseData(self):
    """
    """
    return self.hasTextContent()

  security.declareProtected(Permissions.AccessContentsInformation, 'getContentType')
  def getContentType(self, default=_MARKER): # pylint: disable=arguments-differ
    """Backward compatibility, read content_type
    from text_format property
    """
    if not self.hasContentType():
      # getProperty can not be used
      # because text_format is not registered in local_properties
      if default is _MARKER:
        return getattr(self, 'text_format', None)
      else:
        return getattr(self, 'text_format', default)
    else:
      if default is _MARKER:
        return self._baseGetContentType()
      else:
        return self._baseGetContentType(default)

  # base_convertable support
  security.declareProtected(Permissions.AccessContentsInformation, 'isSupportBaseDataConversion')
  def isSupportBaseDataConversion(self):
    """
    """
    return True

  def _convertToBaseFormat(self):
    """Conversion to base format for TextDocument consist
    to convert file content into utf-8.
    If the data embeds charset information, this information is updated
    to the new (utf-8) charset. This supports XML and HTML.
    """
    def guessCharsetAndConvert(document, text_content, content_type):
      # type: (TextDocument, bytes, str) -> Tuple[bytes, str]
      """
      return encoded content_type and message if encoding
      is not utf-8
      """
      codec = guessEncodingFromText(text_content, content_type)
      if codec is not None:
        try:
          text_content = text_content.decode(codec).encode('utf-8')
        except (UnicodeDecodeError, LookupError):
          message = 'Conversion to base format with codec %r fails' % codec
          # try again with another guesser based on file command
          codec = guessEncodingFromText(text_content, 'text/plain')
          if codec is not None:
            try:
              text_content = text_content.decode(codec).encode('utf-8')
            except (UnicodeDecodeError, LookupError):
              message = 'Conversion to base format with codec %r fails'\
                                                                      % codec
            else:
              message = 'Conversion to base format with codec %r succeeds'\
                                                                      % codec
        else:
          message = 'Conversion to base format with codec %r succeeds'\
                                                                      % codec
      else:
        message = 'Conversion to base format without codec fails'
      return text_content, message

    content_type = self.getContentType() or DEFAULT_CONTENT_TYPE
    data = bytes(self.getData())
    if content_type.endswith('xml'):
      try:
        tree = etree.fromstring(data)
        data = etree.tostring(tree, encoding='utf-8', xml_declaration=True)
        message = 'Conversion to base format succeeds'
      except etree.XMLSyntaxError: # pylint: disable=catching-non-exception
        message = 'Conversion to base format without codec fails'
    elif content_type == 'text/html':
      re_match = self.charset_parser.search(data)
      message = 'Conversion to base format succeeds'
      if re_match is not None:
        charset = re_match.group('charset').decode('ascii')
        try:
          # Use encoding in html document
          data = data.decode(charset).encode('utf-8')
        except (UnicodeDecodeError, LookupError):
          # Encoding read from document is wrong
          data, message = guessCharsetAndConvert(self, data, content_type)
        else:
          message = 'Conversion to base format with charset %r succeeds'\
                                                                  % charset
          if charset.lower() != 'utf-8':
            charset = 'utf-8' # Override charset if convertion succeeds
            # change charset value in html_document as well
            def subCharset(matchobj):
              keyword = matchobj.group('keyword')
              charset = matchobj.group('charset')
              if not (keyword or charset):
                # no match, return same string
                return matchobj.group(0)
              elif keyword:
                # if keyword is present, replace charset just after
                return keyword + b'utf-8'
            data = self.charset_parser.sub(subCharset, data)
      else:
        data, message = guessCharsetAndConvert(self, data, content_type)
    else:
      # generaly text/plain
      try:
        # if succeeds, not need to change encoding
        # it's already utf-8
        data.decode('utf-8')
      except (UnicodeDecodeError, LookupError):
        data, message = guessCharsetAndConvert(self, data, content_type)
      else:
        message = 'Conversion to base format succeeds'
    self._setBaseData(data)
    self._setBaseContentType(content_type)
    return message

  security.declareProtected(Permissions.AccessContentsInformation, 'getTextContent')
  def getTextContent(self, default=_MARKER):
    """Overridden method to check permission to access content in raw format
    """
    self._checkConversionFormatPermission(None)
    if default is _MARKER:
      return self._baseGetTextContent()
    else:
      return self._baseGetTextContent(default)

  # Backward compatibility for replacement of text_format by content_type
  security.declareProtected(Permissions.AccessContentsInformation, 'getTextFormat')
  def getTextFormat(self, default=_MARKER):
    """
    """
    LOG('TextDocument', WARNING,
              'Usage of text_format is deprecated, use content_type instead')
    return self.getContentType(default)

  security.declareProtected(Permissions.ModifyPortalContent, 'setTextFormat')
  def setTextFormat(self, value):
    """
    """
    LOG('TextDocument', WARNING,
              'Usage of text_format is deprecated, use content_type instead')
    return self.setContentType(value)

  security.declareProtected(Permissions.ModifyPortalContent, '_setTextFormat')
  def _setTextFormat(self, value):
    """
    """
    LOG('TextDocument', WARNING,
              'Usage of text_format is deprecated, use content_type instead')
    return self._setContentType(value)

  def getData(self, default=_MARKER):
    # type: (bytes) -> bytes | PData
    """getData must returns original content but TextDocument accepts
    data or text_content to store original content.
    Fallback on text_content property if data is not defined
    """
    if not self.hasData():
      if default is _MARKER:
        data = self._baseGetTextContent()
      else:
        data = self._baseGetTextContent(default)
        if data is default:
          return default
      return str2bytes(data) if data is not None else None
    else:
      if default is _MARKER:
        return File.getData(self)
      else:
        return File.getData(self, default)

  def updateContentMd5(self):
    """Update md5 checksum from the original file

    Overriden here because CachedConvertableMixin version does not
    understand the dynamic nature TextDocument's data.
    """
    self._setContentMd5(md5(self.getData() or b'').hexdigest())
