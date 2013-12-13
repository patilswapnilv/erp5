# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2010 Nexedi SARL and Contributors. All Rights Reserved.
#          Aurelien Calonne <aurel@nexedi.com>
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
##############################################################################

import os
import shutil
import unittest
import random
import transaction
from App.config import getConfiguration
from Products.ERP5VCS.WorkingCopy import getVcsTool

from Products.ERP5.Document.BusinessTemplate import \
    BusinessTemplateMissingDependency

from Products.ERP5.Tool.TemplateTool import BusinessTemplateUnknownError

from Products.ERP5Type.tests.ERP5TypeTestCase import ERP5TypeTestCase

class TestTemplateTool(ERP5TypeTestCase):
  """
  Test the template tool
  """
  run_all_test = 1
  quiet = 1
  test_tool_id = 'test_portal_templates'

  def getBusinessTemplateList(self):
    return ('erp5_core_proxy_field_legacy',
            'erp5_full_text_myisam_catalog',
            'erp5_base',
            'erp5_stock_cache',
            'erp5_csv_style')

  def getTitle(self):
    return "Template Tool"

  def afterSetUp(self):
    self.templates_tool = self.portal.portal_templates
    self.setupAutomaticBusinessTemplateRepository(
         searchable_business_template_list=["erp5_core", "erp5_base"])
    if getattr(self.portal, self.test_tool_id, None) is not None:
      self.portal.manage_delObjects(ids=[self.test_tool_id])
    self.portal.newContent(portal_type='Template Tool',
                           id=self.test_tool_id)
    self.dummy_template_tool = getattr(self.portal, self.test_tool_id)

  def beforeTearDown(self):
    self.tic()
    mark_replaced_bt_list = ["erp5_odt_style", "erp5_pdm", 'erp5_accounting',
           'erp5_workflow', 'erp5_configurator', 'erp5_configurator_ung',
           'erp5_ingestion_mysql_innodb_catalog', "erp5_configurator_standard"]
    for bt_name in mark_replaced_bt_list:
      bt = self.templates_tool.getInstalledBusinessTemplate(bt_name)
      if (bt is not None) and bt.getInstallationState() in ['installed',
                                                            'replaced']:
        self.templates_tool.manage_delObjects([bt.getId()])
    self.tic()
    bt = self.templates_tool.getInstalledBusinessTemplate("erp5_base")
    if bt.getInstallationState() == "replaced":
      bt.install(force=1)
    self.tic()

  def checkFolderReindexAllActivityPresense(self):
    message_list = [m for m in self.portal.portal_activities.getMessageList()
                      if m.method_id == 'Folder_reindexAll']
    self.assertNotEquals(len(message_list), 0)

  def checkFolderReindexAllActivityNotPresent(self):
    message_list = [m for m in self.portal.portal_activities.getMessageList()
                      if m.method_id == 'Folder_reindexAll']
    self.assertEquals(len(message_list), 0)

  def testUpdateBT5FromRepository(self, quiet=quiet, run=run_all_test):
    """ Test the list of bt5 returned for upgrade """
    # edit bt5 revision so that it will be marked as updatable
    bt_list = self.templates_tool.searchFolder(title='erp5_base')
    self.assertEquals(len(bt_list), 1)
    erp5_base = bt_list[0].getObject()
    try:
      erp5_base.edit(revision=0)

      updatable_bt_list = \
        self.templates_tool.getRepositoryBusinessTemplateList(update_only=True)
      self.assertEqual(
           [i.title for i in updatable_bt_list if i.title == "erp5_base"],
           ["erp5_base"])
      erp5_base.replace()
      updatable_bt_list = \
        self.templates_tool.getRepositoryBusinessTemplateList(update_only=True)
      self.assertEqual(
           [i.title for i in updatable_bt_list if i.title == "erp5_base"],
           [])
    finally:
      erp5_base.edit(revision=int(erp5_base.getRevision()) + 10)

  def test_download_http(self):
    test_web = self.portal.portal_templates.download(
        'http://www.erp5.org/dists/snapshot/test_bt5/test_web.bt5')
    self.assertEquals(test_web.getPortalType(), 'Business Template')
    self.assertEquals(test_web.getTitle(), 'test_web')
    self.assertTrue(test_web.getRevision())

  def _svn_setup_ssl(self):
    """
      Function used to trust in svn.erp5.org.
    """
    trust_dict = dict(realm="https://svn.erp5.org:443",
      hostname="roundcube.nexedi.com",
      issuer_dname="Nexedi SA, Marcq en Baroeul, Nord Pas de Calais, FR",
      valid_from="Thu, 22 May 2008 13:43:01 GMT",
      valid_until="Sun, 20 May 2018 13:43:01 GMT",
      finger_print=\
        "a1:f7:c6:bb:51:69:84:28:ac:58:af:9d:05:73:de:24:45:4d:a1:bb",
      failures=8)
    getVcsTool("svn").__of__(self.portal).acceptSSLServer(trust_dict)

  def test_download_svn(self):
    # if the page looks like a svn repository, template tool will use pysvn to
    # get the bt5.
    self._svn_setup_ssl()
    bt5_url = 'https://svn.erp5.org/repos/public/erp5/trunk/bt5/test_web'
    test_web = self.portal.portal_templates.download(bt5_url)
    self.assertEquals(test_web.getPortalType(), 'Business Template')
    self.assertEquals(test_web.getTitle(), 'test_web')
    self.assertTrue(test_web.getRevision())

  def test_updateBusinessTemplateFromUrl_simple(self):
    """
     Test updateBusinessTemplateFromUrl method

     By default if a new business template has revision >= previous one
     the new bt5 is not installed, only imported.
    """
    self._svn_setup_ssl()
    template_tool = self.portal.portal_templates
    old_bt = template_tool.getInstalledBusinessTemplate('erp5_csv_style')
    # change revision to an old revision
    old_bt.setRevision(0.0001)
    url = 'https://svn.erp5.org/repos/public/erp5/trunk/bt5/erp5_csv_style'
    template_tool.updateBusinessTemplateFromUrl(url)
    new_bt = template_tool.getInstalledBusinessTemplate('erp5_csv_style')
    self.assertNotEquals(old_bt, new_bt)
    self.assertEquals('erp5_csv_style', new_bt.getTitle())

    # Test Another time with definning an ID
    old_bt = new_bt
    old_bt.setRevision(0.0002)
    template_tool.updateBusinessTemplateFromUrl(url, id="new_erp5_csv_style")
    new_bt = template_tool.getInstalledBusinessTemplate('erp5_csv_style')
    self.assertNotEquals(old_bt, new_bt)
    self.assertEquals('erp5_csv_style', new_bt.getTitle())
    self.assertEquals('new_erp5_csv_style', new_bt.getId())

    # Test if the new instance with same revision is not installed.
    old_bt = new_bt
    template_tool.updateBusinessTemplateFromUrl(url, id="not_installed_bt5")
    new_bt = template_tool.getInstalledBusinessTemplate('erp5_csv_style')
    self.assertEquals(old_bt, new_bt)
    self.assertEquals('erp5_csv_style', new_bt.getTitle())
    self.assertEquals('new_erp5_csv_style', new_bt.getId())
    not_installed_bt5 = getattr(template_tool, "not_installed_bt5", None)
    self.assertNotEquals(not_installed_bt5, None)
    self.assertEquals('erp5_csv_style', not_installed_bt5.getTitle())
    self.assertEquals(not_installed_bt5.getInstallationState(),
                      "not_installed")
    self.assertEquals(not_installed_bt5.getRevision(), new_bt.getRevision())

  def test_updateBusinessTemplateFromUrl_keep_list(self):
    """
     Test updateBusinessTemplateFromUrl method
    """
    self._svn_setup_ssl()
    template_tool = self.portal.portal_templates
    url = 'https://svn.erp5.org/repos/public/erp5/trunk/bt5/test_core'
    # don't install test_file
    keep_original_list = ('portal_skins/erp5_test/test_file', )
    template_tool.updateBusinessTemplateFromUrl(url,
                                   keep_original_list=keep_original_list)
    bt = template_tool.getInstalledBusinessTemplate('test_core')
    self.assertNotEquals(None, bt)
    erp5_test = getattr(self.portal.portal_skins, 'erp5_test', None)
    self.assertNotEquals(None, erp5_test)
    test_file = getattr(erp5_test, 'test_file', None)
    self.assertEquals(None, test_file)

  def test_updateBusinessTemplateFromUrl_after_before_script(self):
    """
     Test updateBusinessTemplateFromUrl method
    """
    from Products.ERP5Type.tests.utils import createZODBPythonScript
    portal = self.getPortal()
    self._svn_setup_ssl()
    createZODBPythonScript(portal.portal_skins.custom,
                                   'BT_dummyA',
                                   'scripts_params=None',
                                   '# Script body\n'
                                   'return context.setDescription("MODIFIED")')

    createZODBPythonScript(portal.portal_skins.custom,
                                   'BT_dummyB',
                                   'scripts_params=None',
                                   '# Script body\n'
                                   'return context.setChangeLog("MODIFIED")')

    createZODBPythonScript(portal.portal_skins.custom,
                                   'BT_dummyC',
                                   'scripts_params=None',
                                   '# Script body\n'
                                   'return context.getPortalObject().setTitle("MODIFIED")')

    template_tool = self.portal.portal_templates
    url = 'https://svn.erp5.org/repos/public/erp5/trunk/bt5/test_html_style'
    # don't install test_file
    before_triggered_bt5_id_list = ['BT_dummyA', 'BT_dummyB']
    after_triggered_bt5_id_list = ['BT_dummyC']
    template_tool.updateBusinessTemplateFromUrl(url,
                                   before_triggered_bt5_id_list=before_triggered_bt5_id_list,
                                   after_triggered_bt5_id_list=after_triggered_bt5_id_list)
    bt = template_tool.getInstalledBusinessTemplate('test_html_style')
    self.assertNotEquals(None, bt)
    self.assertEquals(bt.getDescription(), 'MODIFIED')
    self.assertEquals(bt.getChangeLog(), 'MODIFIED')
    self.assertEquals(portal.getTitle(), 'MODIFIED')

  def test_updateBusinessTemplateFromUrl_stringCastingBug(self):
    pt = self.getTemplateTool()
    template = pt.newContent(portal_type='Business Template')
    self.failUnless(template.getBuildingState() == 'draft')
    self.failUnless(template.getInstallationState() == 'not_installed')
    title = 'install_casting_to_int_bug_check'
    template.edit(title=title,
                  version='1.0',
                  description='bt for unit_test')
    self.commit()

    template.build()
    self.commit()

    cfg = getConfiguration()
    template_path = os.path.join(cfg.instancehome, 'tests', '%s' % (title,))
    # remove previous version of bt it exists
    if os.path.exists(template_path):
      shutil.rmtree(template_path)
    template.export(path=template_path, local=1)
    self.failUnless(os.path.exists(template_path))

    # setup version '9'
    first_revision = '9'
    open(os.path.join(template_path, 'bt', 'revision'), 'w').write(first_revision)
    pt.updateBusinessTemplateFromUrl(template_path)
    new_bt = pt.getInstalledBusinessTemplate(title)

    self.assertEqual(new_bt.getRevision(), first_revision)

    # setup revision '11', becasue: '11' < '9' (string comp), but 11 > 9 (int comp)
    second_revision = '11'
    self.assertTrue(second_revision < first_revision)
    self.assertTrue(int(second_revision) > int(first_revision))

    open(os.path.join(template_path, 'bt', 'revision'), 'w').write(second_revision)
    pt.updateBusinessTemplateFromUrl(template_path)
    newer_bt = pt.getInstalledBusinessTemplate(title)

    self.assertNotEqual(new_bt, newer_bt)
    self.assertEqual(newer_bt.getRevision(), second_revision)

  def test_CompareVersions(self):
    """Tests compare version on template tool. """
    compareVersions = self.getPortal().portal_templates.compareVersions
    self.assertEquals(0, compareVersions('1', '1'))
    self.assertEquals(0, compareVersions('1.2', '1.2'))
    self.assertEquals(0, compareVersions('1.2rc3', '1.2rc3'))
    self.assertEquals(0, compareVersions('1.0.0', '1.0'))

    self.assertEquals(-1, compareVersions('1.0', '1.0.1'))
    self.assertEquals(-1, compareVersions('1.0rc1', '1.0'))
    self.assertEquals(-1, compareVersions('1.0a', '1.0.1'))
    self.assertEquals(-1, compareVersions('1.1', '2.0'))

  def test_CompareVersionStrings(self):
    """Test compareVersionStrings on template tool"""
    compareVersionStrings = \
        self.getPortal().portal_templates.compareVersionStrings
    self.assertTrue(compareVersionStrings('1.1', '> 1.0'))
    self.assertFalse(compareVersionStrings('1.1rc1', '= 1.0'))
    self.assertFalse(compareVersionStrings('1.0rc1', '> 1.0'))
    self.assertFalse(compareVersionStrings('1.0rc1', '>= 1.0'))
    self.assertTrue(compareVersionStrings('1.0rc1', '>= 1.0rc1'))

  def test_getInstalledBusinessTemplate(self):
    self.assertNotEquals(None, self.getPortal()\
        .portal_templates.getInstalledBusinessTemplate('erp5_core'))

    self.assertEquals(None, self.getPortal()\
        .portal_templates.getInstalledBusinessTemplate('erp5_toto'))

  def test_getInstalledBusinessTemplateRevision(self):
    self.assertTrue(300 < self.getPortal()\
        .portal_templates.getInstalledBusinessTemplateRevision('erp5_core'))

    self.assertEquals(None, self.getPortal()\
        .portal_templates.getInstalledBusinessTemplateRevision('erp5_toto'))

  def test_getInstalledBusinessTemplateList(self):
    templates_tool = self.getPortal().portal_templates
    bt5_list = templates_tool.getInstalledBusinessTemplateList()
    another_bt_list = [i for i in templates_tool.contentValues() \
                       if i.getInstallationState() == 'installed']
    self.assertEquals(len(bt5_list), len(another_bt_list))
    for bt in bt5_list:
      self.failUnless(bt in another_bt_list)

    self.assertEquals(bt5_list,
                      templates_tool._getInstalledBusinessTemplateList())

  def test_getInstalledBusinessTemplateTitleList(self):
    templates_tool = self.getPortal().portal_templates
    bt5_list = templates_tool.getInstalledBusinessTemplateTitleList()
    another_bt_list = [i.getTitle() for i in templates_tool.contentValues() \
                       if i.getInstallationState() == 'installed']
    bt5_list.sort()
    another_bt_list.sort()
    self.assertEquals(bt5_list, another_bt_list)
    for bt in bt5_list:
      self.failUnless(bt in another_bt_list)

    new_list = templates_tool._getInstalledBusinessTemplateList(only_title=1)
    new_list.sort()
    self.assertEquals(bt5_list, new_list)

  def test_getBusinessTemplateUrl(self):
    """ Test if this method can find which repository is the business
        template
    """
    # How to define an existing and use INSTANCE_HOME_REPOSITORY?
    url_list = ['https://svn.erp5.org/repos/public/erp5/trunk/bt5',
                'http://www.erp5.org/dists/snapshot/bt5',
                'http://www.erp5.org/dists/release/5.4.5/bt5',
                "INSTANCE_HOME_REPOSITORY",
                'file:///opt/does/not/exist']

    exist_bt5 = 'erp5_base'
    not_exist_bt5 = "erp5_not_exist"
    template_tool = self.portal.portal_templates
    getBusinessTemplateUrl = template_tool.getBusinessTemplateUrl

    # Test Exists
    self.assertEquals(getBusinessTemplateUrl(url_list, exist_bt5),
                  'https://svn.erp5.org/repos/public/erp5/trunk/bt5/erp5_base')
    self.assertEquals(getBusinessTemplateUrl(url_list[1:], exist_bt5),
                      'http://www.erp5.org/dists/snapshot/bt5/erp5_base.bt5')
    self.assertEquals(getBusinessTemplateUrl(url_list[2:], exist_bt5),
                      'http://www.erp5.org/dists/release/5.4.5/bt5/erp5_base.bt5')
    INSTANCE_HOME = getConfiguration().instancehome
    local_bt = None
    if os.path.exists(INSTANCE_HOME + "/bt5/erp5_base"):
      local_bt = 'file://' + INSTANCE_HOME + "/bt5/erp5_base"
    self.assertEquals(getBusinessTemplateUrl(url_list[3:], exist_bt5), local_bt)
    self.assertEquals(getBusinessTemplateUrl(url_list[4:], exist_bt5), None)

    # Test Not exists
    self.assertEquals(getBusinessTemplateUrl(url_list, not_exist_bt5), None)
    self.assertEquals(getBusinessTemplateUrl(url_list[1:], not_exist_bt5), None)
    self.assertEquals(getBusinessTemplateUrl(url_list[2:], not_exist_bt5), None)
    self.assertEquals(getBusinessTemplateUrl(url_list[3:], not_exist_bt5), None)
    self.assertEquals(getBusinessTemplateUrl(url_list[4:], not_exist_bt5), None)

  def test_resolveBusinessTemplateListDependency(self):
    """ Test API able to return a complete list of bt5s to setup a sub set of
    business templates.
    """
    repository = "dummy_repository"
    template_tool = self.dummy_template_tool
    # setup dummy internal repository data to make unit test independant
    # from any real repository
    def addRepositoryEntry(**kw):
      kw['id'] = '%s.bt5' % kw['title']
      kw.setdefault('version', '1')
      kw.setdefault('provision_list', ())
      kw.setdefault('dependency_list', ())
      kw.setdefault('revision', '1')
      return kw
    template_tool.repository_dict[repository] = (
      addRepositoryEntry(title='foo', dependency_list=()),
      addRepositoryEntry(title='bar', dependency_list=('foo',)),
      addRepositoryEntry(title='baz', dependency_list=('bar',)),
      addRepositoryEntry(title='biz', dependency_list=()),
      addRepositoryEntry(title='ca1', provision_list=('sql',)),
      addRepositoryEntry(title='ca2', provision_list=('sql',)),
      addRepositoryEntry(title='a', dependency_list=()),
      addRepositoryEntry(title='b', dependency_list=('a'), revision='5'),
      addRepositoryEntry(title='end', dependency_list=('baz','sql', 'b')),
      )

    # Simulate that we have some installed bt.
    for bt_id in ('foo', 'ca1', 'b'):
      bt = template_tool.newContent(portal_type='Business Template',
                             title=bt_id, revision='4', id=bt_id)
      bt.install()
    
    bt5_id_list = ['baz']
    bt5_list = template_tool.resolveBusinessTemplateListDependency(bt5_id_list)
    self.assertEquals([(repository, 'foo.bt5'),
                       (repository, 'bar.bt5'),
                       (repository, 'baz.bt5')], bt5_list)

    bt5_id_list = ['foo']
    bt5_list = template_tool.resolveBusinessTemplateListDependency(
                      bt5_id_list)
    self.assertEquals([(repository, 'foo.bt5')], bt5_list)

    bt5_id_list = ['biz', 'end']

    bt5_list = template_tool.resolveBusinessTemplateListDependency(bt5_id_list)
    self.assertEquals([(repository, 'foo.bt5'),
                       (repository, 'a.bt5'),
                       (repository, 'bar.bt5'),
                       (repository, 'b.bt5'),
                       (repository, 'ca1.bt5'),
                       (repository, 'baz.bt5'),
                       (repository, 'end.bt5'),
                       (repository, 'biz.bt5')], bt5_list)

    # By removing ca1, we remove the choice for the "sql" provider.
    # Therefore template tool does not know any more what to take for "sql".
    template_tool.manage_delObjects(['ca1'])
    self.commit()
    self.assertRaises(BusinessTemplateMissingDependency,
                template_tool.resolveBusinessTemplateListDependency,
                bt5_id_list)

    bt5_id_list = ['erp5_do_not_exist']
    self.assertRaises(BusinessTemplateUnknownError,
                   template_tool.resolveBusinessTemplateListDependency,
                   bt5_id_list)

  def test_installBusinessTemplatesFromRepository_simple(self):
    """ Simple test for portal_templates.installBusinessTemplatesFromRepository
    """
    bt5_name = 'erp5_odt_style'
    self.tic()
    bt = self.templates_tool.getInstalledBusinessTemplate(bt5_name, strict=True)
    self.assertEquals(bt, None)
    operation_log = \
      self.templates_tool.installBusinessTemplateListFromRepository([bt5_name])
    self.assertTrue("Installed %s with" % bt5_name in operation_log[-1])
    bt = self.templates_tool.getInstalledBusinessTemplate(bt5_name, strict=True)
    self.assertNotEquals(bt, None)
    self.assertEquals(bt.getTitle(), bt5_name)

    # Repeat operation, the bt5 should be ignored
    self.templates_tool.installBusinessTemplateListFromRepository([bt5_name])
    bt_old = self.templates_tool.getInstalledBusinessTemplate(bt5_name, strict=True)
    self.assertEquals(bt.getId(), bt_old.getId())

    # Repeat operation, new bt5 should be inslalled due only_newer = False
    operation_log = self.templates_tool.installBusinessTemplateListFromRepository(
          [bt5_name], only_newer=False)

    self.assertTrue("Installed %s with" % bt5_name in operation_log[-1])
    bt_new = self.templates_tool.getInstalledBusinessTemplate(bt5_name,
                                                              strict=True)
    self.assertNotEquals(bt.getId(), bt_new.getId())

  def test_installBusinessTemplatesFromRepository_update_catalog(self):
    """ Test if update catalog is trigger when needed.
    """
    try:
      bt5_name = 'erp5_ingestion_mysql_innodb_catalog'
      template_tool = self.portal.portal_templates
      self.tic()
      bt = template_tool.getInstalledBusinessTemplate(bt5_name)
      self.assertEquals(bt, None)
      operation_log = template_tool.installBusinessTemplateListFromRepository([bt5_name],
                            only_newer=False, update_catalog=0)

      self.assertTrue("Installed %s with" % bt5_name in operation_log[0])
      bt = template_tool.getInstalledBusinessTemplate(bt5_name)
      self.assertNotEquals(bt.getId(), None)
      self.commit()
      self.checkFolderReindexAllActivityNotPresent()
      # Before launch activities make sure email table is created even
      # catalog is not created.
      catalog_tool = self.portal.portal_catalog
      catalog_tool.erp5_mysql_innodb.z0_drop_email()
      catalog_tool.erp5_mysql_innodb.z_create_email()
      self.tic()

      bt5_name = 'erp5_odt_style'
      operation_log = template_tool.installBusinessTemplateListFromRepository([bt5_name],
                            only_newer=False, update_catalog=1)
      self.assertTrue("Installed %s with" % bt5_name in operation_log[-1])
      bt = template_tool.getInstalledBusinessTemplate(bt5_name)
      self.assertEquals(bt.getTitle(), bt5_name)
      self.commit()
      self.checkFolderReindexAllActivityPresense()
      self.tic()

      # Install again should not force catalog to be updated
      operation_log = template_tool.installBusinessTemplateListFromRepository(
                [bt5_name], only_newer=False)
      self.assertTrue("Installed %s with" % bt5_name in operation_log[-1])
      bt = template_tool.getInstalledBusinessTemplate(bt5_name)
      self.assertNotEquals(bt, None)
      self.assertEquals(bt.getTitle(), bt5_name)
      self.commit()
      self.checkFolderReindexAllActivityNotPresent()
      self.tic()
    finally:
      # Make sure no broken catalog it will be left behind and propaguated to
      # the next tests.
      if len(self.portal.portal_activities.getMessageList())>0:
        self.portal.portal_activities.manageClearActivities()
        self.commit()
        self.portal.ERP5Site_reindexAll(clear_catalog=1)
      self.tic()

  def test_installBusinessTemplatesFromRepository_activate(self):
    """ Test if update catalog is trigger when needed.
    """
    bt5_name_list = ['erp5_odt_style', 'erp5_pdm']
    self.tic()
    for bt5_name in bt5_name_list:
      bt = self.templates_tool.getInstalledBusinessTemplate(bt5_name)
      self.assertEquals(bt, None)

    self.templates_tool.installBusinessTemplateListFromRepository(
                            bt5_name_list, activate=True)

    for bt5_name in bt5_name_list:
      bt = self.templates_tool.getInstalledBusinessTemplate(bt5_name)
      self.assertEquals(bt, None)

    self.tic()
    for bt5_name in bt5_name_list:
      bt = self.templates_tool.getInstalledBusinessTemplate(bt5_name)
      self.assertNotEquals(bt, None)
      self.assertEquals(bt.getTitle(), bt5_name)

  def test_installBusinessTemplatesFromRepository_install_dependency(self):
    """Test if dependencies are automatically installed properly
    """
    # erp5_configurator_{ung,standard} depends on erp5_configurator which in
    # turn depends on erp5_workflow
    bt5_name_list = ['erp5_configurator_ung', 'erp5_configurator_standard']
    template_tool = self.portal.portal_templates
    for repos in template_tool.getRepositoryList():
      if "bootstrap" not in repos:
        repository = repos
    self.tic()
    for bt5_name in bt5_name_list:
      bt = template_tool.getInstalledBusinessTemplate(bt5_name)
      self.assertEquals(bt, None)

    bt = template_tool.getInstalledBusinessTemplate("erp5_configurator")
    self.assertEquals(bt, None)
    bt = template_tool.getInstalledBusinessTemplate("erp5_workflow")
    self.assertEquals(bt, None)

    self.assertRaises(BusinessTemplateMissingDependency,
              template_tool.installBusinessTemplateListFromRepository,
                            bt5_name_list)

    # Try fail in activities.
    self.assertRaises(BusinessTemplateMissingDependency,
              template_tool.installBusinessTemplateListFromRepository,
                      bt5_name_list, True, True, True)

    for bt5_name in bt5_name_list:
      bt = template_tool.getInstalledBusinessTemplate(bt5_name)
      self.assertEquals(bt, None)
      dependency_list = template_tool.getDependencyList(
                   (repository, bt5_name))
      self.assertNotEquals(dependency_list, [])

    template_tool.installBusinessTemplateListFromRepository(
                            bt5_name_list, install_dependency=True)
    for bt5_name in bt5_name_list:
      bt = template_tool.getInstalledBusinessTemplate(bt5_name)
      self.assertNotEquals(bt, None)

    bt = template_tool.getInstalledBusinessTemplate("erp5_configurator")
    self.assertNotEquals(bt, None)
    bt = template_tool.getInstalledBusinessTemplate("erp5_workflow")
    self.assertNotEquals(bt, None)
    transaction.abort()

    # Same as above but also check that dependencies are properly resolved if
    # one of the dependency is explicitly added to the list of bt5 to be
    # installed
    template_tool.installBusinessTemplateListFromRepository(
      bt5_name_list + ['erp5_workflow'],
      install_dependency=True)
    for bt5_name in bt5_name_list:
      bt = template_tool.getInstalledBusinessTemplate(bt5_name)
      self.assertNotEquals(bt, None)

    bt = template_tool.getInstalledBusinessTemplate("erp5_configurator")
    self.assertNotEquals(bt, None)
    bt = template_tool.getInstalledBusinessTemplate("erp5_workflow")
    self.assertNotEquals(bt, None)
    transaction.abort()

  def test_installBusinessTemplateListFromRepository_ignore_when_installed(self):
    """Check that install one business template, this method does not download
    many business templates that are already installed
    """
    template_tool = self.portal.portal_templates
    # Delete not installed bt5 to check easily if more not installed was
    # created
    for bt5 in template_tool.getBuiltBusinessTemplateList():
      bt5.delete()
    bt5_name_list = ['erp5_calendar']
    template_tool.installBusinessTemplateListFromRepository(bt5_name_list,
        install_dependency=True)
    self.tic()
    self.assertEquals(template_tool.getBuiltBusinessTemplateList(), [])

  def test_sortBusinessTemplateList(self):
    """Check sorting of a list of business template by their dependencies
    """
    template_tool = self.portal.portal_templates

    bt5list = template_tool.resolveBusinessTemplateListDependency(('erp5_credential',))
    # add some entropy by disorder bt5list returned by
    # resolveBusinessTemplateListDependency
    position_list = range(len(bt5list))
    new_bt5_list = []
    while position_list:
      position = random.choice(position_list)
      position_list.remove(position)
      new_bt5_list.append(bt5list[position])

    ordered_list = template_tool.sortBusinessTemplateList(new_bt5_list)
    # group orders
    first_group = range(0, 6)
    second_group =  range(6, 8)
    third_group = range(8, 10)
    fourth_group = range(10, 12)
    fifth_group = range(12, 13)

    expected_position_dict = dict((('erp5_property_sheets', first_group),
                                   ('erp5_core_proxy_field_legacy', first_group),
                                   ('erp5_mysql_innodb_catalog', first_group),
                                   ('erp5_core', first_group),
                                   ('erp5_full_text_myisam_catalog', first_group),
                                   ('erp5_xhtml_style', first_group),
                                   ('erp5_ingestion_mysql_innodb_catalog', second_group),
                                   ('erp5_base', second_group),
                                   ('erp5_jquery', third_group),
                                   ('erp5_ingestion', third_group),
                                   ('erp5_web', fourth_group),
                                   ('erp5_crm', fourth_group),
                                   ('erp5_credential', fifth_group)))

    for bt in ordered_list:
      self.assertTrue(ordered_list.index(bt) in expected_position_dict[bt[1]],
            'Expected positions for %r: %r, got %r' % (bt[1], 
                                                  expected_position_dict[bt[1]],
                                                  ordered_list.index(bt)))

def test_suite():
  suite = unittest.TestSuite()
  suite.addTest(unittest.makeSuite(TestTemplateTool))
  return suite
