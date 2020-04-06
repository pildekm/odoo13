# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint
import requests
import werkzeug

from odoo import http
from odoo.http import request
import hashlib
from werkzeug import urls

_logger = logging.getLogger(__name__)


class WSpayController(http.Controller):
    _return_url = '/payment/wspay/return/'
    _cancel_url = '/payment/wspay/cancel/'
    _error_url = '/payment/wspay/error/'

    def _wspay_validate_data(self, **post):

        _logger.info(
            'WSPay response: {Success}; '
            'ShoppingCartID: {ShoppingCartID}; '
            'ApprovalCode: {ApprovalCode}; '
            'Signature: {Signature}'.format(**post))

        payment_acquirer = request.env['payment.acquirer'].sudo().search([('provider', '=', 'wspay')])
        signature_str = '{shop_id}{secret_key}{shopping_cart_id}{secret_key}{success}{secret_key}{approval_code}{secret_key}'  # noqa
        signature_str = signature_str.format(
            shop_id=payment_acquirer.shop_id,
            secret_key=payment_acquirer.secret_key,
            shopping_cart_id=post['ShoppingCartID'],
            success=post['Success'],
            approval_code=post['ApprovalCode'],
        )
        signature = hashlib.md5()
        signature.update(signature_str.encode('utf-8'))
        signature = signature.hexdigest()
        # verify the transaction.
        if (post['Success'] != '1' or post['ApprovalCode'] == '' or post['Signature'] != signature):
            return werkzeug.utils.redirect(self._error_url)
        res = request.env['payment.transaction'].sudo().form_feedback(post, 'wspay')
        return res

    def _wspay_validate_notification(self, **post):
        wspay = request.env['payment.acquirer'].sudo().search([('provider', '=', 'wspay')])
        response = requests.post(wspay.wspay_get_form_action_url())
        response.raise_for_status()
        _logger.info('Validate WSPay Notification %s' % response.text)
        return {}

    @http.route(['/payment/wspay/return',], type='http', auth='public', methods=['GET','POST'])
    def wspay_return(self, **post):
        """WSPay return """
        _logger.info('Beginning WSPAY form_feedback with post data %s', pprint.pformat(post))
        res = self._wspay_validate_data(**post)
        return werkzeug.utils.redirect('/payment/process')


    @http.route(['/payment/wspay/cancel',], type='http', auth='public', methods=['GET','POST'])
    def wspay_cancel(self, **post):
        """ WSPay Cancel """
        _logger.info('Beginning Alipay notification form_feedback with post data %s', pprint.pformat(post))
        self._wspay_validate_notification(**post)
        #return werkzeug.utils.redirect('/payment/process')

    @http.route(['/payment/wspay/error',], type='http', auth='public', methods=['GET', 'POST'])
    def wspay_error(self, **post):
        """ WSPay Notify """
        _logger.info('WSPay error %s', pprint.pformat(post))
        self._wspay_validate_notification(**post)
        #return werkzeug.utils.redirect('/payment/process')
