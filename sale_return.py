# -*- coding: utf-8 -*-
"""
    sale_return.py

"""
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta

__all__ = ['ReturnPolicy', 'ReturnPolicyTerm', 'ReturnReason']
__metaclass__ = PoolMeta


class ReturnPolicy(ModelSQL, ModelView):
    """
    Sale Return Policy
    """
    __name__ = 'sale.return.policy'

    name = fields.Char('Name', required=True, select=True)
    description = fields.Text('Description')
    terms = fields.One2Many('sale.return.policy.term', 'policy', 'Terms')


class ReturnPolicyTerm(ModelSQL, ModelView):
    """
    Sale Return Policy Term
    """
    __name__ = 'sale.return.policy.term'

    policy = fields.Many2One('sale.return.policy', 'Policy', select=True)
    reason = fields.Many2One('sale.return.reason', 'Reason', select=True)
    days = fields.Integer('Days', required=True)
    since = fields.Selection([
        ('shipping', 'Shipping'),
        ('sale', 'Sale'),
    ], 'Days Since', required=True)
    shipping_paid_by_customer = fields.Boolean('Shipping Paid by Customer?')


class ReturnReason(ModelSQL, ModelView):
    """
    Sale Return Reason
    """
    __name__ = 'sale.return.reason'

    name = fields.Char('Name', required=True, select=True)
    description = fields.Text('Description')
