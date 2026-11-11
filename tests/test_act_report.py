"""Verify aggregation of the actual DCS query using SQLite fixtures.

Only register virtual tables are replaced by fixture selects; this does not test
1C's virtual-table implementation, metadata loading or DCS rendering.
"""
from pathlib import Path
import re
import sqlite3
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / 'fonecmid-diplom/src'
SCHEMA = ROOT / 'Reports/ВКМ_АнализАктов/Templates/ОсновнаяСхемаКомпоновкиДанных/Template.dcs'
NS = {'d': 'http://v8.1c.ru/8.1/data-composition-system/schema'}


def query_for_fixtures():
    query = ET.parse(SCHEMA).findtext('.//d:query', namespaces=NS)
    assert 'Документ.' not in query and 'Регистратор.' not in query
    query = query.replace(
        'РегистрНакопления.ВКМ_ВыполненныеКлиентуРаботы.Обороты(&НачалоПериода, &КонецПериода, , )',
        '(SELECT * FROM works WHERE period BETWEEN :start AND :end)')
    query = query.replace(
        'РегистрНакопления.ВКМ_ВыставленныеАкты.Обороты(&НачалоПериода, &КонецПериода, , ВКМ_Номенклатура = &ВКМ_НоменклатураРаботыСпециалиста)',
        '(SELECT * FROM acts WHERE period BETWEEN :start AND :end AND ВКМ_Номенклатура = :work_item)')
    for source, target in [('СГРУППИРОВАТЬ ПО', 'GROUP BY'), ('ОБЪЕДИНИТЬ ВСЕ', 'UNION ALL'),
                           ('ВЫБРАТЬ', 'SELECT'), ('СУММА', 'SUM'), ('КАК', 'AS'), ('ИЗ', 'FROM')]:
        query = re.sub(r'\b' + source + r'\b', target, query)
    assert 'Регистр' not in query
    return query


class ActReportTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript('''
            CREATE TABLE works(period TEXT, ВКМ_Клиент TEXT, ВКМ_Договор TEXT, ВКМ_СуммаКОплатеОборот REAL);
            CREATE TABLE acts(period TEXT, ВКМ_Контрагент TEXT, ВКМ_Договор TEXT, ВКМ_Номенклатура TEXT, ВКМ_СуммаОборот REAL);
        ''')

    def rows(self):
        return self.db.execute(query_for_fixtures(), {'start': '2026-11-01', 'end': '2026-11-30T23:59:59',
                                                     'work_item': 'work'}).fetchall()

    def test_multiple_rows_and_contracts_do_not_multiply(self):
        self.db.executemany('INSERT INTO works VALUES (?, ?, ?, ?)', [
            ('2026-11-01', 'A', 'one', 100), ('2026-11-02', 'A', 'one', 200),
            ('2026-11-02', 'A', 'two', 50)])
        self.db.executemany('INSERT INTO acts VALUES (?, ?, ?, ?, ?)', [
            ('2026-11-05', 'A', 'one', 'work', 80), ('2026-11-06', 'A', 'one', 'work', 120),
            ('2026-11-05', 'A', 'one', 'subscription', 1000), ('2026-11-05', 'A', 'two', 'work', 40)])
        self.assertCountEqual(self.rows(), [('A', 'one', 300, 200), ('A', 'two', 50, 40)])

    def test_contract_with_only_act_is_present(self):
        self.db.execute('INSERT INTO acts VALUES (?, ?, ?, ?, ?)', ('2026-11-05', 'B', 'three', 'work', 90))
        self.assertEqual(self.rows(), [('B', 'three', 0, 90)])

    def test_period_and_nomenclature_are_respected(self):
        self.db.executemany('INSERT INTO acts VALUES (?, ?, ?, ?, ?)', [
            ('2026-10-31', 'A', 'one', 'work', 500), ('2026-12-01', 'A', 'one', 'work', 500),
            ('2026-11-30T23:59:59', 'A', 'one', 'work', 70), ('2026-11-01', 'A', 'one', 'subscription', 800)])
        self.assertEqual(self.rows(), [('A', 'one', 0, 70)])


if __name__ == '__main__':
    unittest.main()
