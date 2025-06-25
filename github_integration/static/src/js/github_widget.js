/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class GitHubStatusWidget extends Component {
    static template = "github_integration.GitHubStatusWidget";
    static props = standardFieldProps;
   
    setup() {
        this.statusColors = {
            'success': 'text-success',
            'failure': 'text-danger',
            'pending': 'text-warning',
            'in_progress': 'text-info',
            'unknown': 'text-muted'
        };
    }
   
    get statusClass() {
        return this.statusColors[this.props.record.data.last_deployment_status] || 'text-muted';
    }
}

registry.category("fields").add("github_status", {
    component: GitHubStatusWidget,
});