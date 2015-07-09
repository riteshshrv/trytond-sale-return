# -*- coding: utf-8 -*-
"""
    tests/test_sale_return.py
"""
import unittest
import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, USER, DB_NAME, CONTEXT
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.exceptions import UserError


class TestSaleReturn(unittest.TestCase):

    def setUp(self):
        """
        Set up data used in the tests.
        this method is called before each test function execution.
        """
        trytond.tests.test_tryton.install_module('sale_return')

        self.Currency = POOL.get('currency.currency')
        self.Company = POOL.get('company.company')
        self.Party = POOL.get('party.party')
        self.User = POOL.get('res.user')
        self.ProductTemplate = POOL.get('product.template')
        self.Uom = POOL.get('product.uom')
        self.ProductCategory = POOL.get('product.category')
        self.Product = POOL.get('product.product')
        self.Country = POOL.get('country.country')
        self.Subdivision = POOL.get('country.subdivision')
        self.Journal = POOL.get('account.journal')
        self.Sale = POOL.get('sale.sale')
        self.SaleLine = POOL.get('sale.line')
        self.SaleConfiguration = POOL.get('sale.configuration')
        self.ReturnPolicy = POOL.get('sale.return.policy')
        self.ReturnPolicyTerm = POOL.get('sale.return.policy.term')
        self.ReturnReason = POOL.get('sale.return.reason')

    def _create_fiscal_year(self, date=None, company=None):
        """
        Creates a fiscal year and requried sequences
        """
        FiscalYear = POOL.get('account.fiscalyear')
        Sequence = POOL.get('ir.sequence')
        SequenceStrict = POOL.get('ir.sequence.strict')
        Company = POOL.get('company.company')

        if date is None:
            date = datetime.date.today()

        if company is None:
            company, = Company.search([], limit=1)

        invoice_sequence, = SequenceStrict.create([{
            'name': '%s' % date.year,
            'code': 'account.invoice',
            'company': company,
        }])
        fiscal_year, = FiscalYear.create([{
            'name': '%s' % date.year,
            'start_date': date + relativedelta(month=1, day=1),
            'end_date': date + relativedelta(month=12, day=31),
            'company': company,
            'post_move_sequence': Sequence.create([{
                'name': '%s' % date.year,
                'code': 'account.move',
                'company': company,
            }])[0],
            'out_invoice_sequence': invoice_sequence,
            'in_invoice_sequence': invoice_sequence,
            'out_credit_note_sequence': invoice_sequence,
            'in_credit_note_sequence': invoice_sequence,
        }])
        FiscalYear.create_period([fiscal_year])
        return fiscal_year

    def _create_coa_minimal(self, company):
        """Create a minimal chart of accounts
        """
        AccountTemplate = POOL.get('account.account.template')
        Account = POOL.get('account.account')

        account_create_chart = POOL.get(
            'account.create_chart', type="wizard")

        account_template, = AccountTemplate.search(
            [('parent', '=', None)]
        )

        session_id, _, _ = account_create_chart.create()
        create_chart = account_create_chart(session_id)
        create_chart.account.account_template = account_template
        create_chart.account.company = company
        create_chart.transition_create_account()

        receivable, = Account.search([
            ('kind', '=', 'receivable'),
            ('company', '=', company),
        ])
        payable, = Account.search([
            ('kind', '=', 'payable'),
            ('company', '=', company),
        ])
        create_chart.properties.company = company
        create_chart.properties.account_receivable = receivable
        create_chart.properties.account_payable = payable
        create_chart.transition_create_properties()

    def _get_account_by_kind(self, kind, company=None, silent=True):
        """Returns an account with given spec
        :param kind: receivable/payable/expense/revenue
        :param silent: dont raise error if account is not found
        """
        Account = POOL.get('account.account')
        Company = POOL.get('company.company')

        if company is None:
            company, = Company.search([], limit=1)

        accounts = Account.search([
            ('kind', '=', kind),
            ('company', '=', company)
        ], limit=1)
        if not accounts and not silent:
            raise Exception("Account not found")
        return accounts[0] if accounts else False

    def _create_payment_term(self):
        """Create a simple payment term with all advance
        """
        PaymentTerm = POOL.get('account.invoice.payment_term')

        return PaymentTerm.create([{
            'name': 'Direct',
            'lines': [('create', [{'type': 'remainder'}])]
        }])

    def setup_defaults(self):
        """Creates default data for testing
        """
        self.country, = self.Country.create([{
            'name': 'United States of America',
            'code': 'US',
        }])
        self.subdivision, = self.Subdivision.create([{
            'country': self.country.id,
            'name': 'California',
            'code': 'CA',
            'type': 'state',
        }])

        self.currency, = self.Currency.create([{
            'name': 'US Dollar',
            'code': 'USD',
            'symbol': '$',
        }])

        with Transaction().set_context(company=None):
            company_party, = self.Party.create([{
                'name': 'fulfil.io'
            }])

        self.company, = self.Company.create([{
            'party': company_party,
            'currency': self.currency,
        }])

        self.User.write([self.User(USER)], {
            'company': self.company,
            'main_company': self.company,
        })
        CONTEXT.update(self.User.get_preferences(context_only=True))

        # Create Fiscal Year
        self._create_fiscal_year(company=self.company.id)
        # Create Chart of Accounts
        self._create_coa_minimal(company=self.company.id)
        # Create a payment term
        self.payment_term, = self._create_payment_term()

        self.cash_journal, = self.Journal.search(
            [('type', '=', 'cash')], limit=1
        )
        self.Journal.write([self.cash_journal], {
            'debit_account': self._get_account_by_kind('other').id
        })

        # Create party
        self.party, = self.Party.create([{
            'name': 'Bruce Wayne',
            'addresses': [('create', [{
                'name': 'Bruce Wayne',
                'party': Eval('id'),
                'city': 'Gotham',
                'invoice': True,
                'country': self.country.id,
                'subdivision': self.subdivision.id,
            }])],
            'customer_payment_term': self.payment_term.id,
            'account_receivable': self._get_account_by_kind(
                'receivable').id,
            'contact_mechanisms': [('create', [
                {'type': 'email', 'value': 'ua@ol.in'},
            ])],
        }])

        self.uom, = self.Uom.search([('name', '=', 'Unit')])
        self.product_category, = self.ProductCategory.create([{
            'name': 'Automobile',
            'account_revenue': self._get_account_by_kind(
                'revenue', company=self.company.id).id,
            'account_expense': self._get_account_by_kind(
                'expense', company=self.company.id).id,
        }])

        self.product_template, = self.ProductTemplate.create([{
            'name': 'Bat Mobile',
            'type': 'goods',
            'salable': True,
            'category': self.product_category.id,
            'default_uom': self.uom.id,
            'sale_uom': self.uom.id,
            'list_price': Decimal('20000'),
            'cost_price': Decimal('15000'),
            'account_category': True,
        }])

        self.product, = self.Product.create([{
            'template': self.product_template.id,
            'code': '123',
        }])

        # Create return policies
        self.reason_1, self.reason_2, self.reason_3, self.reason_4 = \
            self.ReturnReason.create([{
                'name': 'Reason 1',
                'description': 'Reason 1 description',
            }, {
                'name': 'Reason 2',
                'description': 'Reason 2 description',
            }, {
                'name': 'Reason 3',
                'description': 'Reason 3 description',
            }, {
                'name': 'Reason 4',
                'description': 'Reason 4 description',
            }])

        self.policy_1, self.policy_2 = self.ReturnPolicy.create([{
            'name': 'Some Policy',
            'description': 'Some Policy description',
            'terms': [('create', [{
                'reason': self.reason_1,
                'days': 7,
                'since': 'sale',
            }, {
                'reason': self.reason_2,
                'days': 30,
                'since': 'shipping',
            }])]
        }, {
            'name': 'Some other Policy',
            'description': 'Some other Policy description',
            'terms': [('create', [{
                'reason': self.reason_3,
                'days': 7,
                'since': 'sale',
            }, {
                'reason': self.reason_4,
                'days': 30,
                'since': 'sale',
            }])]
        }])

        # Fill inventory with our product
        Inventory = POOL.get('stock.inventory')
        StockLocation = POOL.get('stock.location')

        warehouse, = StockLocation.search([
            ('type', '=', 'warehouse'),
        ])
        inventory, = Inventory.create([{
            'location': warehouse.storage_location,
            'company': self.company.id,
            'lines': [('create', [{
                'product': self.product.id,
                'quantity': 100,
            }])]
        }])
        Inventory.confirm([inventory])

        # Update Sale Configuration
        self.sale_configuration = self.SaleConfiguration(1)
        self.sale_configuration.default_return_policy = self.policy_1.id
        self.sale_configuration.save()

    def test_0010_test_product_return_policy(self):
        """
        Test the return policy on products
        """
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.setup_defaults()

            self.assertIsNone(self.product.effective_return_policy)

            # Write a return policy on product
            self.product_category.return_policy = self.policy_1.id
            self.product_category.save()

            self.assertEqual(
                self.product.effective_return_policy.id, self.policy_1.id
            )

            # Write a return policy on product
            self.product_template.return_policy = self.policy_2.id
            self.product_template.save()

            self.assertEqual(
                self.product.effective_return_policy.id, self.policy_2.id
            )

    def test_0020_test_non_return_sale_line(self):
        """
        Test sale line
        """
        Date = POOL.get('ir.date')

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.setup_defaults()

            sale, = self.Sale.create([{
                'reference': 'Test Sale',
                'payment_term': self.payment_term.id,
                'currency': self.company.currency.id,
                'party': self.party.id,
                'invoice_address': self.party.addresses[0].id,
                'shipment_address': self.party.addresses[0].id,
                'sale_date': Date.today(),
                'company': self.company.id,
            }])
            # Create sale line
            values = {
                'sale': sale.id,
                'type': 'line',
            }
            values.update(self.SaleLine(**values).on_change_quantity())
            values.update(self.SaleLine(**values).on_change_product())
            self.assertEqual(
                values['return_policy_at_sale'],
                self.sale_configuration.default_return_policy.id)
            values.update(self.SaleLine(**values).on_change_origin())
            self.assertIsNone(values['return_policy'])

            # Write a return policy on product
            self.product_template.return_policy = self.policy_2.id
            self.product_template.save()

            values['product'] = self.product.id
            values.update(self.SaleLine(**values).on_change_product())
            self.assertEqual(
                values['return_policy_at_sale'],
                self.product_template.return_policy.id)

            values['quantity'] = 1
            values.update(self.SaleLine(**values).on_change_quantity())
            self.assertFalse(values.get('is_return'))

            sale_line = self.SaleLine(**values)
            sale_line.save()

            self.assertTrue(sale_line)
            self.assertFalse(sale_line.is_return)
            self.assertFalse(sale.has_return)

            self.assertTrue(sale_line.effective_return_policy_at_sale)
            self.assertEqual(
                sale_line.effective_return_policy_at_sale,
                sale_line.return_policy_at_sale
            )
            # Set return_policy_at_sale as None
            sale_line.return_policy_at_sale = None
            sale_line.save()
            self.assertTrue(sale_line.effective_return_policy_at_sale)
            self.assertEqual(
                sale_line.effective_return_policy_at_sale,
                self.product.effective_return_policy
            )

    def test_0030_test_return_sale_fulfilling_policy(self):
        """
        Test returning a sale
        """
        Date = POOL.get('ir.date')

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            self.setup_defaults()

            sale, = self.Sale.create([{
                'reference': 'Test Sale',
                'payment_term': self.payment_term.id,
                'currency': self.company.currency.id,
                'party': self.party.id,
                'invoice_address': self.party.addresses[0].id,
                'shipment_address': self.party.addresses[0].id,
                'sale_date': Date.today(),
                'company': self.company.id,
            }])

            # Create sale line
            values = {
                'sale': sale.id,
                'type': 'line',
                'quantity': 1,
                'product': self.product.id
            }

            values.update(self.SaleLine(**values).on_change_product())
            values.update(self.SaleLine(**values).on_change_quantity())

            sale_line = self.SaleLine(**values)
            sale_line.save()

            self.assertTrue(sale_line)
            self.assertFalse(sale_line.is_return)
            self.assertFalse(sale_line.returns)

            # Quote, Confirm and Process Sale
            self.Sale.quote([sale])
            self.Sale.confirm([sale])
            self.Sale.process([sale])

            # Create a return sale
            return_sale, = self.Sale.create([{
                'reference': 'Test Sale',
                'payment_term': self.payment_term.id,
                'currency': self.company.currency.id,
                'party': self.party.id,
                'invoice_address': self.party.addresses[0].id,
                'shipment_address': self.party.addresses[0].id,
                'sale_date': Date.today(),
                'company': self.company.id,
            }])

            # Create sale line
            values = {
                'sale': return_sale.id,
                'type': 'line',
                'quantity': -1,
                'product': self.product.id
            }
            values.update(self.SaleLine(**values).on_change_product())
            values.update(self.SaleLine(**values).on_change_quantity())
            values['origin'] = '%s,%s' % (self.SaleLine.__name__, -1)

            values.update(self.SaleLine(**values).on_change_origin())
            self.assertIsNone(values['return_policy'])
            self.assertTrue(values['is_return'])

            values['origin'] = '%s,%s' % (self.SaleLine.__name__, sale_line.id)
            values.update(self.SaleLine(**values).on_change_origin())
            self.assertIsNotNone(values['return_policy'])
            self.assertEqual(
                values['return_policy'],
                sale_line.effective_return_policy_at_sale.id)

            values['return_reason'] = self.reason_2.id
            values['return_type'] = self.SaleLine.default_return_type()

            return_sale_line = self.SaleLine(**values)
            return_sale_line.save()

            self.assertTrue(return_sale_line)
            self.assertTrue(return_sale_line.is_return)
            self.assertTrue(return_sale.has_return)

            # Quote, Confirm and Process Sale
            self.Sale.quote([return_sale])
            self.Sale.confirm([return_sale])
            self.Sale.process([return_sale])

            self.assertTrue(return_sale.shipment_returns)
            self.assertTrue(return_sale.invoices)
            self.assertEqual(len(return_sale.invoices), 1)
            self.assertEqual(return_sale.invoices[0].type, 'out_credit_note')
            self.assertTrue(sale_line.returns)
            self.assertEqual(len(sale_line.returns), 1)
            self.assertEqual(sale_line.returns[0].id, return_sale.id)

            # Create a new return sale with the same origin
            return_sale1, = self.Sale.create([{
                'reference': 'Test Sale',
                'payment_term': self.payment_term.id,
                'currency': self.company.currency.id,
                'party': self.party.id,
                'invoice_address': self.party.addresses[0].id,
                'shipment_address': self.party.addresses[0].id,
                'sale_date': Date.today(),
                'company': self.company.id,
            }])

            # Create sale line
            values = {
                'sale': return_sale1.id,
                'type': 'line',
                'quantity': -1,
                'product': self.product.id,
            }
            values.update(self.SaleLine(**values).on_change_product())
            values.update(self.SaleLine(**values).on_change_quantity())

            values['origin'] = '%s,%s' % (self.SaleLine.__name__, sale_line.id)
            values.update(self.SaleLine(**values).on_change_origin())

            return_sale_line1 = self.SaleLine(**values)
            return_sale_line1.save()

            self.assertTrue(return_sale_line1)
            self.assertTrue(return_sale_line1.is_return)
            self.assertTrue(return_sale1.has_return)

            # Quote, Confirm and Process Sale
            self.Sale.quote([return_sale1])
            try:
                self.Sale.confirm([return_sale1])
            except UserError, e:
                self.assertTrue(
                    e.message.endswith(
                        'returned on Sale #%s.' % return_sale.reference)
                )


def suite():
    "Define suite"
    test_suite = trytond.tests.test_tryton.suite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestSaleReturn)
    )
    return test_suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
