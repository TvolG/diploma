"""Offline structural checks. Does not compile EDT metadata or run the 1C platform."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / 'fonecmid-diplom' / 'src'
DOCS = ('ВКМ_ОбслуживаниеКлиента', 'ВКМ_НачислениеЗарплаты', 'ВыплатаЗарплаты', 'ГрафикОтпусков')
forms = [ROOT / 'Documents' / doc / 'Forms/ФормаДокумента/Form.form' for doc in DOCS]
forms += [ROOT / 'Catalogs/ДоговорыКонтрагентов/Forms/ФормаЭлемента/Form.form',
          ROOT / 'DataProcessors/ВКМ_МассовоеСозданиеАктов/Forms/Форма/Form.form']
xml_count = 0
for folder in ('Documents', 'Catalogs', 'DataProcessors', 'Reports', 'Roles', 'Subsystems', 'Configuration', 'AccumulationRegisters'):
    names = set(DOCS) | {'ДоговорыКонтрагентов', 'ВКМ_МассовоеСозданиеАктов', 'ВКМ_АнализАктов',
                        'ВКМ_ОтделКадров', 'ВКМ_ОбслуживаниеКлиентов', 'ВКМ_ЗарплатаИОтпуска', 'ВКМ_ДобавленныеОбъекты', 'ВКМ_ВыставленныеАкты', 'Configuration'}
    for directory in (ROOT / folder).iterdir() if folder != 'Configuration' else [ROOT / folder]:
        if directory.name not in names:
            continue
        for path in directory.rglob('*'):
            if path.suffix in {'.mdo', '.form', '.rights', '.dcs', '.cmi'}:
                ET.parse(path)
                xml_count += 1
for path in forms:
    root = ET.parse(path).getroot()
    module = path.with_name('Module.bsl').read_text(encoding='utf-8-sig')
    procedures = set(re.findall(r'(?:Процедура|Функция)\s+(\w+)\s*\(', module))
    for kind in ('name', 'id'):
        values = [item.findtext(kind) for item in root.iter('items')]
        assert len(values) == len(set(values)), (path, 'duplicate element ' + kind)
    for handler in root.iter('handlers'):
        assert handler.findtext('name') in procedures, (path, 'missing event handler', handler.findtext('name'))
    commands = {command.findtext('name'): command for command in root.findall('formCommands')}
    for command in commands.values():
        for name in command.findall('./action/handler/name'):
            assert name.text in procedures, (path, 'missing command handler', name.text)
    for command in root.iter('commandName'):
        if command.text.startswith('Form.Command.'):
            assert command.text.removeprefix('Form.Command.') in commands, (path, 'unknown form command')
    if '/Documents/' in path.as_posix():
        doc = path.parents[2].name
        mdo = ET.parse(ROOT / 'Documents' / doc / (doc + '.mdo')).getroot()
        known = {'Number', 'Date', 'Ref', 'Posted', 'DeletionMark', 'RegisterRecords'}
        known |= {n.findtext('name') for n in mdo.findall('attributes')}
        tables = {t.findtext('name'): {a.findtext('name') for a in t.findall('attributes')}
                  for t in mdo.findall('tabularSections')}
        for segment in root.iter('segments'):
            parts = segment.text.split('.')
            if parts[0] == 'Объект':
                assert parts[1] in known | tables.keys(), (path, segment.text)
                if len(parts) > 2 and parts[1] in tables:
                    assert parts[2] in tables[parts[1]] | {"LineNumber"}, (path, segment.text)
print(f'PASS: {xml_count} XML files; {len(forms)} forms: unique elements, handlers, commands and document data paths')

# New register must be a real metadata dependency of its writer, not just a query name.
act_ref = 'AccumulationRegister.ВКМ_ВыставленныеАкты'
act_register = ET.parse(ROOT / 'AccumulationRegisters/ВКМ_ВыставленныеАкты/ВКМ_ВыставленныеАкты.mdo').getroot()
for item in act_register.findall('dimensions') + act_register.findall('resources'):
    assert item.findtext('name').startswith('ВКМ_')
    for type_name in item.findall('./type/types'):
        if type_name.text.startswith('CatalogRef.'):
            catalog = type_name.text.split('.', 1)[1]
            assert (ROOT / 'Catalogs' / catalog / (catalog + '.mdo')).exists(), type_name.text
configuration = ET.parse(ROOT / 'Configuration/Configuration.mdo').getroot()
assert act_ref in [node.text for node in configuration.findall('accumulationRegisters')]
realization = ET.parse(ROOT / 'Documents/РеализацияТоваровУслуг/РеализацияТоваровУслуг.mdo').getroot()
assert act_ref in [node.text for node in realization.findall('registerRecords')]
source_index = {}
for path in ROOT.rglob('*.mdo'):
    root = ET.parse(path).getroot()
    source_index[root.tag.split('}')[-1] + '.' + root.findtext('name', '')] = path
service = ET.parse(ROOT / 'Subsystems/ВКМ_ДобавленныеОбъекты/ВКМ_ДобавленныеОбъекты.mdo').getroot()
for content in service.findall('content'):
    assert content.text in source_index, ('missing object in service subsystem', content.text)
writer = (ROOT / 'Documents/РеализацияТоваровУслуг/ObjectModule.bsl').read_text()
known_fields = {'Период'} | {n.findtext('name') for n in act_register.findall('dimensions') + act_register.findall('resources')}
assert set(re.findall(r'ДвижениеАкта\.(\w+)\s*=', writer)) <= known_fields
print('PASS: new act register types, writer registration, movement fields and service subsystem references')
