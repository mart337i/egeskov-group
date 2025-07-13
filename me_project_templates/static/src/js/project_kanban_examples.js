/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { renderToMarkup } from '@web/core/utils/render';
import { markup } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";

const greenBullet = markup(`<span class="o_status d-inline-block o_status_green"></span>`);
const orangeBullet = markup(`<span class="o_status d-inline-block text-warning"></span>`);
const star = markup(`<a style="color: gold;" class="fa fa-star"></a>`);
const clock = markup(`<a class="fa fa-clock-o"></a>`);

const bulletMap = {
    'greenBullet': greenBullet,
    'orangeBullet': orangeBullet,
    'star': star,
    'clock': clock,
};

// Get the original examples data that was already registered
const originalData = registry.category("kanban_examples").get('project', null);

async function getConfigurableTemplates() {
    try {
        const result = await rpc("/project_templates/kanban_examples", {});
        
        // Convert bullet strings to markup objects
        if (result.examples) {
            result.examples.forEach(example => {
                if (example.bullets) {
                    example.bullets = example.bullets.map(bulletKey => bulletMap[bulletKey]).filter(Boolean);
                }
                // Convert description to markup if it's HTML
                if (example.description) {
                    example.description = markup(example.description);
                } else {
                    // Use generic template if no description provided
                    example.description = renderToMarkup("project.example.generic");
                }
            });
        }
        
        return result.examples || [];
    } catch (error) {
        console.warn("Could not load configurable project templates:", error);
        return [];
    }
}

async function enhanceExampleData() {
    // If original data doesn't exist, create fallback
    const baseData = originalData || {
        ghostColumns: [_t('New'), _t('Assigned'), _t('In Progress'), _t('Done')],
        applyExamplesText: _t("Use This For My Project"),
        allowedGroupBys: ['stage_id'],
        foldField: "fold",
        examples: [{
            name: _t('Software Development'),
            columns: [_t('Backlog'), _t('Specifications'), _t('Development'), _t('Tests')],
            foldedColumns: [_t('Delivered')],
            get description() {
                return renderToMarkup("project.example.generic");
            },
            bullets: [greenBullet, orangeBullet, star],
        }, {
            name: _t('Agile Scrum'),
            columns: [_t('Backlog'), _t('Sprint Backlog'), _t('Sprint in Progress')],
            foldedColumns: [_t('Sprint Complete'), _t('Old Completed Sprint')],
            get description() {
                return renderToMarkup("project.example.agilescrum");
            },
            bullets: [greenBullet, orangeBullet],
        }, {
            name: _t('Digital Marketing'),
            columns: [_t('Ideas'), _t('Researching'), _t('Writing'), _t('Editing')],
            foldedColumns: [_t('Done')],
            get description() {
                return renderToMarkup("project.example.digitalmarketing");
            },
            bullets: [greenBullet, orangeBullet],
        }, {
            name: _t('Customer Feedback'),
            columns: [_t('New'), _t('In development')],
            foldedColumns: [_t('Done'), _t('Refused')],
            get description() {
                return renderToMarkup("project.example.customerfeedback");
            },
            bullets: [greenBullet, orangeBullet],
        }, {
            name: _t('Consulting'),
            columns: [_t('New Projects'), _t('Resources Allocation'), _t('In Progress')],
            foldedColumns: [_t('Done')],
            get description() {
                return renderToMarkup("project.example.consulting");
            },
            bullets: [greenBullet, orangeBullet],
        }, {
            name: _t('Research Project'),
            columns: [_t('Brainstorm'), _t('Research'), _t('Draft')],
            foldedColumns: [_t('Final Document')],
            get description() {
                return renderToMarkup("project.example.researchproject");
            },
            bullets: [greenBullet, orangeBullet],
        }, {
            name: _t('Website Redesign'),
            columns: [_t('Page Ideas'), _t('Copywriting'), _t('Design')],
            foldedColumns: [_t('Live')],
            get description() {
                return renderToMarkup("project.example.researchproject");
            },
        }, {
            name: _t('T-shirt Printing'),
            columns: [_t('New Orders'), _t('Logo Design'), _t('To Print')],
            foldedColumns: [_t('Done')],
            get description() {
                return renderToMarkup("project.example.tshirtprinting");
            },
            bullets: [star],
        }, {
            name: _t('Design'),
            columns: [_t('New Request'), _t('Design'), _t('Client Review')],
            foldedColumns: [_t('Handoff')],
            get description() {
                return renderToMarkup("project.example.generic");
            },
            bullets: [greenBullet, orangeBullet, star, clock],
        }, {
            name: _t('Publishing'),
            columns: [_t('Ideas'), _t('Writing'), _t('Editing')],
            foldedColumns: [_t('Published')],
            get description() {
                return renderToMarkup("project.example.generic");
            },
            bullets: [greenBullet, orangeBullet, star, clock],
        }, {
            name: _t('Manufacturing'),
            columns: [_t('New Orders'), _t('Material Sourcing'), _t('Manufacturing'), _t('Assembling')],
            foldedColumns: [_t('Delivered')],
            get description() {
                return renderToMarkup("project.example.generic");
            },
            bullets: [greenBullet, orangeBullet, star, clock],
        }, {
            name: _t('Podcast and Video Production'),
            columns: [_t('Research'), _t('Script'), _t('Recording'), _t('Mixing')],
            foldedColumns: [_t('Published')],
            get description() {
                return renderToMarkup("project.example.generic");
            },
            bullets: [greenBullet, orangeBullet, star, clock],
        }],
    };
    
    const configurableTemplates = await getConfigurableTemplates();
    
    // Combine original examples with configurable ones
    const allExamples = [...baseData.examples, ...configurableTemplates];
    
    return {
        ...baseData,
        examples: allExamples,
    };
}

// Wait for DOM to be ready and then enhance the examples
document.addEventListener('DOMContentLoaded', function() {
    enhanceExampleData().then(data => {
        registry.category("kanban_examples").add('project', data);
        console.log("Enhanced kanban examples with configurable templates:", data.examples.length, "total examples");
        console.log("Template names:", data.examples.map(e => e.name));
    }).catch(error => {
        console.error("Failed to enhance kanban examples:", error);
        // Fallback to original data if available
        if (originalData) {
            registry.category("kanban_examples").add('project', originalData);
        }
    });
});

// Also try immediate execution for cases where DOM is already ready
if (document.readyState === 'loading') {
    // DOM is still loading, wait for it
} else {
    // DOM is already ready
    enhanceExampleData().then(data => {
        registry.category("kanban_examples").add('project', data);
        console.log("Enhanced kanban examples with configurable templates (immediate):", data.examples.length, "total examples");
    }).catch(error => {
        console.error("Failed to enhance kanban examples (immediate):", error);
    });
}