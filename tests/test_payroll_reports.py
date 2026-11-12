"""Run the actual report SELECTs on independently calculated register fixtures.
Does not emulate native 1C virtual tables or DCS rendering.
"""
from pathlib import Path
import re
import sqlite3
import unittest
import xml.etree.ElementTree as ET
R = Path(__file__).resolve().parents[1] / 'fonecmid-diplom/src/Reports'
D = '{http://v8.1c.ru/8.1/data-composition-system/schema}'


def query(name):
    tree = ET.parse(R / name / 'Templates/ОсновнаяСхемаКомпоновкиДанных/Template.dcs')
    sql = tree.findtext('.//' + D + 'query')
    assert 'Документ.' not in sql
    return sql


def translate(sql):
    for ru, en in [('СГРУППИРОВАТЬ ПО','GROUP BY'), ('ВЫБРАТЬ','SELECT'), ('СУММА','SUM'), ('КАК','AS'), ('ИЗ','FROM')]:
        sql = re.sub(r'\b' + ru + r'\b', en, sql)
    return sql


class SpecialistReport(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute('CREATE TABLE work(day TEXT, ВКМ_Сотрудник TEXT, ВКМ_ЧасовКОплатеОборот REAL, ВКМ_СуммаКОплатеОборот REAL)')
        self.db.executemany('INSERT INTO work VALUES(?,?,?,?)', [
            ('2026-05-01','A',2,200), ('2026-05-31T23:59:59','A',3,300),
            ('2026-05-10','B',4,0), ('2026-04-30','A',9,900), ('2026-06-01','A',8,800)])

    def result(self, specialist):
        sql = query('ВКМ_ВыработкаСпециалистов')
        start = sql.index('РегистрНакопления.')
        stop = sql.index(' КАК Работы', start)
        call = sql[start:stop]
        self.assertIn('&НачалоПериода, &КонецПериода', call)
        self.assertIn('ВКМ_Сотрудник = &Специалист', call)
        self.assertIn('ПустаяСсылка', call)
        sql = sql[:start] + "(SELECT * FROM work WHERE day BETWEEN :start AND :end AND (:employee = '' OR ВКМ_Сотрудник = :employee))" + sql[stop:]
        return self.db.execute(translate(sql), {'start':'2026-05-01', 'end':'2026-05-31T23:59:59', 'employee':specialist}).fetchall()

    def test_selected_specialist_and_period(self):
        self.assertEqual(self.result('A'), [('A',5,500)])

    def test_all_and_explicit_zero_percent(self):
        self.assertCountEqual(self.result(''), [('A',5,500),('B',4,0)])


class SettlementReport(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute('CREATE TABLE movements(day TEXT, employee TEXT, accrued REAL, paid REAL)')
        self.db.executemany('INSERT INTO movements VALUES(?,?,?,?)', [
            ('2026-04-30','A',1000,0), ('2026-05-01','A',8700,0),
            ('2026-05-02','A',0,2000), ('2026-06-01','A',99999,0),
            ('2026-05-01','B',4350,0), ('2026-05-10','B',0,17782.8)])
        self.db.executescript('''CREATE VIEW virtual_balances AS
            SELECT employee AS Сотрудник,
              SUM(CASE WHEN day < '2026-05-01' THEN accrued-paid ELSE 0 END) AS СуммаНачальныйОстаток,
              SUM(CASE WHEN day >= '2026-05-01' THEN accrued ELSE 0 END) AS СуммаПриход,
              SUM(CASE WHEN day >= '2026-05-01' THEN paid ELSE 0 END) AS СуммаРасход,
              SUM(accrued-paid) AS СуммаКонечныйОстаток
            FROM movements WHERE day <= '2026-05-31T23:59:59' GROUP BY employee;''')

    def test_opening_net_accrual_payment_closing(self):
        sql = query('ВКМ_РасчётыССотрудниками')
        virtual = 'РегистрНакопления.ВКМ_ВзаиморасчетыССотрудниками.ОстаткиИОбороты(&НачалоПериода, &КонецПериода, , , )'
        self.assertIn(virtual, sql)
        rows = self.db.execute(translate(sql.replace(virtual, 'virtual_balances'))).fetchall()
        expected = [('A',1000,8700,2000,7700),('B',0,4350,17782.8,-13432.8)]
        for got, want in zip(sorted(rows), expected):
            self.assertEqual(got[0],want[0])
            for a,b in zip(got[1:],want[1:]):self.assertAlmostEqual(a,b,places=2)
        for _,opening,accrued,paid,closing in rows:
            self.assertAlmostEqual(opening+accrued-paid,closing,places=2)
