# -*- coding: utf-8 -*-
"""
    __init__.py

"""
from trytond.pool import Pool
from sale_return import ReturnPolicy, ReturnPolicyTerm, ReturnReason
from sale import SaleLine, SaleConfiguration, Sale
from product import ProductCategory, ProductTemplate


def register():
    Pool.register(
        ReturnReason,
        ReturnPolicy,
        ReturnPolicyTerm,
        ProductCategory,
        ProductTemplate,
        Sale,
        SaleConfiguration,
        SaleLine,
        module='sale_return', type_='model'
    )
