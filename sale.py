# -*- coding: utf-8 -*-
"""
    sale.py

    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool, And

__all__ = ['SaleLine', 'SaleConfiguration', 'Sale']
__metaclass__ = PoolMeta

STATE = ~And(
    Eval('type') == 'line',
    Bool(Eval('product'))
)
DEPENDS = ['type', 'product']


class SaleLine:
    __name__ = 'sale.line'

    return_policy_at_sale = fields.Many2One(
        'sale.return.policy', 'Return Policy at Sale',
        states={
            'invisible': Eval('type') != 'line'
        },
        depends=['type']
    )

    effective_return_policy_at_sale = fields.Function(
        fields.Many2One(
            'sale.return.policy', 'Effective Return Policy at Sale',
            states={
                'invisible': Eval('type') != 'line'
            },
            depends=['type']
        ),
        'get_effective_return_policy_at_sale'
    )

    is_return = fields.Function(
        fields.Boolean('Is Return?'),
        'get_is_return'
    )

    origin = fields.Reference(
        'Origin', selection='get_origin',
        states={
            'invisible': STATE,
        },
        depends=DEPENDS + ['is_return']
    )

    return_policy = fields.Many2One(
        'sale.return.policy', 'Return Policy',
        states={
            'invisible': STATE,
        },
        depends=DEPENDS + ['is_return']
    )

    return_type = fields.Selection([
        ('credit', 'Credit'),
        ('refund', 'Refund'),
        ('exchange', 'Exchange'),
    ], 'Return Type', states={
        'invisible': STATE,
    }, depends=DEPENDS + ['is_return'])

    return_reason = fields.Many2One(
        'sale.return.reason', 'Reason',
        states={
            'invisible': STATE,
        },
        depends=DEPENDS + ['is_return']
    )

    returns = fields.Function(
        fields.One2Many(
            'sale.line', None, 'Returns',
            states={
                'invisible': STATE,
            },
        ),
        'get_returns'
    )

    @staticmethod
    def default_return_type():
        return 'credit'

    @staticmethod
    def default_return_policy_at_sale():
        """
        Returns default policy from sale configuration
        """
        Configuration = Pool().get('sale.configuration')

        return Configuration(1).default_return_policy.id

    def get_effective_return_policy_at_sale(self, name):
        """
        Returns the sale's return policy if there, else the effective return
        policy of product
        """
        if self.return_policy_at_sale:
            return self.return_policy_at_sale.id
        if self.product and self.product.effective_return_policy:
            return self.product.effective_return_policy.id

    def get_is_return(self, name=None):
        """
        Returns True if it's a Return Sale Line
        """
        return (
            self.type == 'line' and self.product and
            self.product.type == 'goods' and self.quantity < 0
        )

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return [cls.__name__]

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')

        models = cls._get_origin()
        models = Model.search([
            ('model', 'in', models),
        ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @fields.depends('type')
    def on_change_quantity(self):
        res = super(SaleLine, self).on_change_quantity()

        if not self.product:
            return res

        res['is_return'] = self.get_is_return()
        return res

    def on_change_product(self):
        res = super(SaleLine, self).on_change_product()

        if not self.product:
            res['return_policy_at_sale'] = self.default_return_policy_at_sale()
            return res

        if self.product.effective_return_policy:
            res['return_policy_at_sale'] = \
                self.product.effective_return_policy.id
        return res

    @fields.depends('origin')
    def on_change_origin(self):
        """
        Fill the return policy if the origin is a sale line
        """
        SaleLine = Pool().get('sale.line')

        if isinstance(self.origin, SaleLine) and self.origin.id != -1:
            return {
                'return_policy':
                    self.origin.effective_return_policy_at_sale and
                    self.origin.effective_return_policy_at_sale.id
            }
        return {
            'return_policy': None
        }

    def get_returns(self, name):
        """
        Returns the return lines for a sale line
        """
        SaleLine = Pool().get('sale.line')

        lines = SaleLine.search([
            ('origin', '=', '%s,%s' % (self.__name__, self.id)),
            ('sale.state', '!=', 'cancel')
        ])
        return map(int, lines)


class SaleConfiguration:
    __name__ = 'sale.configuration'

    default_return_policy = fields.Many2One(
        'sale.return.policy', 'Default Return Policy', required=True)


class Sale:
    __name__ = 'sale.sale'

    has_return = fields.Function(
        fields.Boolean('Has Return?'),
        'get_has_return'
    )

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()

        cls._error_messages.update({
            'line_with_same_origin':
                "The line set as origin on Sale Line %s has already been "
                "returned on Sale #%s."
        })

    def get_has_return(self, name):
        """
        Returns True if there's a return sale line
        """
        return any((line.is_return for line in self.lines))

    @classmethod
    def confirm(cls, sales):
        """
        Validate for return sale lines, if they fall under return policy
        """
        super(Sale, cls).confirm(sales)

        cls.validate_sale_for_return(sales)

    @classmethod
    def validate_sale_for_return(cls, sales):
        """
        Validate sale lines against return policy
        """
        SaleLine = Pool().get('sale.line')

        for sale in sales:
            if not sale.has_return:
                continue

            for line in filter(lambda l: l.is_return, sale.lines):
                orig_line = line.origin

                line_with_same_origin = SaleLine.search([
                    (
                        'origin',
                        '=',
                        '%s,%s' % (orig_line.__name__, orig_line.id)
                    ),
                    ('id', '!=', line.id)
                ])

                if line_with_same_origin:
                    cls.raise_user_error(
                        'line_with_same_origin',
                        (line.id, line_with_same_origin[0].sale.reference)
                    )
