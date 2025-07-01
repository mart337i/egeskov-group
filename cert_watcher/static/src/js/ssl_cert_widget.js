/** @odoo-module **/

import { Component, onWillStart, useRef } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { _t } from '@web/core/l10n';

const fieldRegistry = registry.category('fields');

class SSLCertStatusWidget extends Component {
    setup() {
        this.status = this.props.record.data[this.props.name];
    }

    get badgeClass() {
        switch (this.status) {
            case 'active': return 'active';
            case 'expired': return 'expired';
            case 'creating':
            case 'renewing': return 'creating';
            case 'error': return 'error';
            default: return '';
        }
    }

    get badgeText() {
        switch (this.status) {
            case 'active': return _t('Active');
            case 'expired': return _t('Expired');
            case 'creating': return _t('Creating');
            case 'renewing': return _t('Renewing');
            case 'error': return _t('Error');
            default: return _t('Draft');
        }
    }
}

SSLCertStatusWidget.template = xml/* xml */ `
    <span class="ssl_cert_status_badge" t-att-class="badgeClass">
        <t t-esc="badgeText"/>
    </span>
`;

fieldRegistry.add('ssl_cert_status', SSLCertStatusWidget);
