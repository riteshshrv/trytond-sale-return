# -*- coding: utf-8 -*-
"""
    product.py

"""
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval

__all__ = ['ProductCategory', 'ProductTemplate']
__metaclass__ = PoolMeta


class ProductCategory:
    __name__ = 'product.category'

    return_policy = fields.Many2One('sale.return.policy', 'Return Policy')


class ProductTemplate:
    __name__ = 'product.template'

    return_policy = fields.Many2One(
        'sale.return.policy', 'Return Policy',
        states={
            'readonly': ~Eval('active', True),
        },
        depends=['active']
    )

    effective_return_policy = fields.Function(
        fields.Many2One(
            'sale.return.policy', 'Effective Return Policy',
            states={
                'readonly': ~Eval('active', True),
            },
            depends=['active']
        ),
        'get_effective_return_policy'
    )

    def get_effective_return_policy(self, name):
        """
        Returns the product's return policy if there else return the product
        category's return policy
        """
        if self.return_policy:
            return self.return_policy.id
        elif self.categories:
            for category in self.categories:
                if category.return_policy:
                    return category.return_policy.id
