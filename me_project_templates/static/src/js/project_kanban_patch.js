/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { markup } from "@odoo/owl";

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

// Patch the kanban examples registry to add configurable templates
const originalGet = registry.category("kanban_examples").get;

registry.category("kanban_examples").get = function(key, defaultValue) {
    if (key === 'project') {
        const originalData = originalGet.call(this, key, defaultValue);
        
        if (!originalData) {
            return defaultValue;
        }
        
        const enhancedData = {
            ...originalData,
            examples: [...originalData.examples]
        };
        
        // Load configurable templates asynchronously
        rpc("/project_templates/kanban_examples", {}).then(result => {
            if (result && result.examples) {
                result.examples.forEach(example => {
                    if (example.bullets) {
                        example.bullets = example.bullets.map(bulletKey => bulletMap[bulletKey]).filter(Boolean);
                    }
                    if (example.description) {
                        example.description = markup(example.description);
                    }
                });
                
                enhancedData.examples.push(...result.examples);
            }
        }).catch(error => {
            console.warn("Could not load configurable project templates:", error);
        });
        
        return enhancedData;
    }
    
    return originalGet.call(this, key, defaultValue);
};