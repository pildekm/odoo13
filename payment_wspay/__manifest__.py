# -*- coding: utf-8 -*-


{
    'name': 'WsPay Payment Acquirer',
    'category': 'Accounting/Payment',
    'summary': 'Payment Acquirer: WsPay Implementation',
    'description': """WSPay Payment Acquirer""",
    'author': "SecondIncome",
    'depends': ['payment'],
    'data': [
        'views/wspay_views.xml',
        'views/payment_wspay_templates.xml',
        'data/payment_acquirer_data.xml',
    ],
    'installable': True,
    'post_init_hook': 'create_missing_journal_for_acquirers',
}
