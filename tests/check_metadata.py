"""Offline structural checks; not a substitute for EDT/1C compilation."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[1] / 'fonecmid-diplom/src'
index = {}
count = 0
for path in ROOT.rglob('*'):
    if path.suffix in {'.mdo', '.form', '.rights', '.dcs', '.cmi'}:
        root = ET.parse(path).getroot()
        count += 1
        if path.suffix == '.mdo':
            ref = root.tag.split('}')[-1] + '.' + root.findtext('name', '')
            assert ref not in index, ('duplicate metadata root', ref)
            index[ref] = path
for ref, path in index.items():
    if not ref.split('.', 1)[-1].startswith('ВКМ_'):
        continue
    root = ET.parse(path).getroot()
    for field in ('content', 'registerRecords'):
        for item in root.findall(field):
            assert item.text in index, (path, 'missing dependency', item.text)
config = ET.parse(ROOT / 'Configuration/Configuration.mdo').getroot()
for node in config:
    if node.text and re.match(r'^(Document|Report|InformationRegister|AccumulationRegister|CalculationRegister|ChartOfCalculationTypes|CommonModule|DataProcessor|Role|Subsystem)\.ВКМ_', node.text):
        assert node.text in index, ('missing configuration object', node.text)
forms = []
for path in ROOT.rglob('*.form'):
    if not any(part.startswith('ВКМ_') for part in path.parts) and not any(part in {'ДоговорыКонтрагентов', 'РеализацияТоваровУслуг'} for part in path.parts):
        continue
    forms.append(path)
    root = ET.parse(path).getroot()
    module = path.with_name('Module.bsl')
    code = module.read_text(encoding='utf-8-sig') if module.exists() else ''
    procedures = set(re.findall(r'(?:Процедура|Функция)\s+(\w+)\s*\(', code, re.I))
    for kind in ('name', 'id'):
        values = [item.findtext(kind) for item in root.iter('items')]
        assert len(values) == len(set(values)), (path, 'duplicate element ' + kind)
    for handler in root.iter('handlers'):
        assert handler.findtext('name') in procedures, (path, 'missing handler', handler.findtext('name'))
    for handler in root.findall('./formCommands/action/handler/name'):
        assert handler.text in procedures, (path, 'missing command handler', handler.text)
    for element in root.iter():
        assert element.attrib.get('{http://www.w3.org/2001/XMLSchema-instance}type') != 'form:FormTable', (path, 'invalid EDT table type')
    if 'Documents' in path.parts and path.parent.name == 'ФормаДокумента':
        doc = path.parents[2].name
        mdo = ET.parse(ROOT / 'Documents' / doc / (doc + '.mdo')).getroot()
        known = {'Number', 'Date', 'Ref', 'Posted', 'DeletionMark', 'RegisterRecords'}
        known |= {n.findtext('name') for n in mdo.findall('attributes')}
        tables = {t.findtext('name'): {a.findtext('name') for a in t.findall('attributes')} for t in mdo.findall('tabularSections')}
        for segment in root.iter('segments'):
            parts = segment.text.split('.')
            if parts[0] == 'Объект':
                assert parts[1] in known | tables.keys(), (path, segment.text)
                if len(parts) > 2 and parts[1] in tables:
                    assert parts[2] in tables[parts[1]] | {'LineNumber'}, (path, segment.text)
graph = (ROOT / 'Documents/ВКМ_ГрафикОтпусков/Forms/ФормаДокумента/Module.bsl').read_text()
assert 'УсловноеОформление.Элементы.Очистить()' in graph
assert not re.search(r'УсловноеОформление\.Очистить\s*\(', graph)
for doc, reg in [('РеализацияТоваровУслуг','ВКМ_ВыставленныеАкты'),('ВКМ_ОбслуживаниеКлиента','ВКМ_ВыполненныеСотрудникомРаботы')]:
    root = ET.parse(index['Document.'+doc]).getroot()
    assert 'AccumulationRegister.'+reg in [n.text for n in root.findall('registerRecords')]
print(f'PASS: {count} XML files parsed; {len(forms)} forms checked; custom dependencies, writers and vacation formatting API checked')

# Every business table must display column headers. The previous generated forms
# parsed as XML but defaulted both table and column headers to false on the platform.
checked_tables = 0
for path in forms:
    root = ET.parse(path).getroot()
    for table in root.iter('items'):
        if table.attrib.get('{http://www.w3.org/2001/XMLSchema-instance}type') != 'form:Table':
            continue
        assert table.findtext('header') == 'true', (path, 'hidden table header')
        for column in table.findall('items'):
            if column.attrib.get('{http://www.w3.org/2001/XMLSchema-instance}type') == 'form:FormField':
                assert column.findtext('showInHeader') == 'true', (path, column.findtext('name'), 'hidden column title')
        checked_tables += 1
for doc in ('ВКМ_НачислениеЗарплаты', 'ВКМ_НачислениеФиксированнойПремии'):
    root = ET.parse(ROOT / 'Documents' / doc / 'Forms/ФормаДокумента/Form.form').getroot()
    for table in root.findall('items'):
        if table.attrib.get('{http://www.w3.org/2001/XMLSchema-instance}type') == 'form:Table':
            for column in table.findall('items'):
                assert column.findtext('title/value'), (doc, 'missing explicit caption', column.findtext('name'))
print(f'PASS: visible headers in {checked_tables} business tables; explicit payroll/premium captions')
