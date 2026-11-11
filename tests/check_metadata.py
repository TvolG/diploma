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
for folder in ('Documents', 'Catalogs', 'DataProcessors', 'Reports', 'Roles', 'Subsystems', 'Configuration'):
    names = set(DOCS) | {'ДоговорыКонтрагентов', 'ВКМ_МассовоеСозданиеАктов', 'ВКМ_АнализАктов',
                        'ВКМ_ОтделКадров', 'ВКМ_ОбслуживаниеКлиентов', 'ЗарплатаИОтпуска', 'Configuration'}
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
