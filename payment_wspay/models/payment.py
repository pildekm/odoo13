# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from hashlib import md5
from werkzeug import urls

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare
from payment_wspay.controllers.main import WSpayController
from odoo.addons.payment.models.payment_acquirer import ValidationError
import hashlib
import re

_logger = logging.getLogger(__name__)


class PaymentAcquirer(models.Model):
    _inherit = 'payment.acquirer'
    """
        A base form with required fields for WSPay integration.
        Set to 'https://formtest.wspay.biz/Authorization.aspx' for testing.
     """

    provider = fields.Selection(selection_add=[('wspay', 'WSPay')])
    shop_id = fields.Char('ShopID', required=True)
    secret_key = fields.Char('SecretKey', required=True)
    user_name = fields.Char('Username', required=True)
    password = fields.Char('Password', required=True)


    def _get_feature_support(self):
        res = super(PaymentAcquirer, self)._get_feature_support()
        res['fees'].append('wspay')
        return res

    @api.model
    def _get_wspay_urls(self, environment):
        """ WSPay URLS """
        if environment == 'prod':
            return 'https://form.WSPay.biz/Authorization.aspx'
        return 'https://formtest.WSPay.biz/Authorization.aspx'

    def wspay_compute_fees(self, amount, currency_id, country_id):
        """ Compute WSPay fees.

            :param float amount: the amount to pay
            :param integer country_id: an ID of a res.country, or None. This is
                                       the customer's country, to be compared to
                                       the acquirer company country.
            :return float fees: computed fees
        """
        fees = 0.0

        return fees

    def signature_total(self, amount):
        total_amount = '{:.2f}'.format(amount).rsplit('.', 1)
        total_amount[0] = total_amount[0].replace(',', '').replace('.', '')
        signature_total_amount = ''.join(total_amount)
        return signature_total_amount

    def _build_sign(self, val):
        signature_str = '{shop_id}{secret_key}{shopping_cart_id}{secret_key}{total_amount}{secret_key}'.format(
            shop_id=self.shop_id,
            secret_key=self.secret_key,
            shopping_cart_id=str(self._get_cart_id(val)),
            total_amount=self.signature_total(val.get('amount', 0)),
        )
        signature = hashlib.md5()
        signature.update(signature_str.encode('utf-8'))
        signature = signature.hexdigest()
        return signature

    def _get_cart_id(self, values):
        cart_id = self.env['sale.order'].search([('name', '=', values['reference'].split('-')[0])]).id
        return cart_id

    def form_total(self, amount):
        total_amount = '{:.2f}'.format(amount).rsplit('.', 1)
        total_amount[0] = total_amount[0].replace(',', '').replace('.', '')
        total_amount = ','.join(total_amount)
        return total_amount

    def wspay_form_generate_values(self, values):

        base_url = self.get_base_url()
        wspay_tx_values = dict(values)
        wspay_tx_values.update({
            'ShopID': self.shop_id,
            'ShoppingCartID': self._get_cart_id(values),
            'TotalAmount': self.form_total(values.get('amount', 0)),
            'Signature': self._build_sign(values),
            'ReturnURL': urls.url_join(base_url, WSpayController._return_url),
            'CancelURL': urls.url_join(base_url, WSpayController._cancel_url),
            'ReturnErrorURL': urls.url_join(base_url, WSpayController._error_url),
            'Lang': values.get('billing_partner_lang')[:2].upper(),
            'CustomerFirstName': values.get('billing_partner_first_name'),
            'CustomerLastName': values.get('billing_partner_last_name'),
            'CustomerAddress': values.get('billing_partner_address'),
            'CustomerCity': values.get('billing_partner_city'),
            'CustomerZIP': values.get('billing_partner_zip'),
            'CustomerCountry': values.get('billing_partner_country').name,
            'CustomerEmail': values.get('billing_partner_email'),
            'CustomerPhone': values.get('billing_partner_phone'),
        })

        return wspay_tx_values

    def wspay_get_form_action_url(self):
        self.ensure_one()
        environment = 'prod' if self.state == 'enabled' else 'test'
        return self._get_wspay_urls(environment)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _check_wspay_configuration(self, vals):
        acquirer_id = int(vals.get('acquirer_id'))
        acquirer = self.env['payment.acquirer'].sudo().browse(acquirer_id)
        if acquirer and acquirer.provider == 'wspay':
            currency_id = int(vals.get('currency_id'))
            if currency_id:
                currency = self.env['res.currency'].sudo().browse(currency_id)
                if currency and currency.name != 'HRK':
                    _logger.info("Only HRK currency is allowed for WSPay Checkout")
                    raise ValidationError(_("""
                        Only transactions in Croatian Kuna (HRK) are allowed for WSPay Checkout.\n
                    """))
        return True

    def write(self, vals):
        if vals.get('currency_id') or vals.get('acquirer_id'):
            for payment in self:
                check_vals = {
                    'acquirer_id': vals.get('acquirer_id', payment.acquirer_id.id),
                    'currency_id': vals.get('currency_id', payment.currency_id.id)
                }
                payment._check_wspay_configuration(check_vals)
        return super(PaymentTransaction, self).write(vals)

    @api.model
    def create(self, vals):
        self._check_wspay_configuration(vals)
        return super(PaymentTransaction, self).create(vals)

    # --------------------------------------------------
    # FORM RELATED METHODS
    # --------------------------------------------------

    @api.model
    def _wspay_form_get_tx_from_data(self, data):
        return {}

    def _wspay_form_get_invalid_parameters(self, data):
        invalid_parameters = []
        # data.get('currency') != self.currency_id.name
        return invalid_parameters

    def _wspay_form_validate(self, data):
        cart_id = data.get('ShoppingCartID')
        cart_obj = self.env['sale.order'].search([('id', '=', cart_id)])
        cart_obj.action_confirm()
        return cart_obj
