/** @odoo-module **/

import { after } from "@html_builder/utils/option_sequence";
import { BaseOptionComponent } from "@html_builder/core/utils";
import { Plugin } from "@html_editor/plugin";
import { withSequence } from "@html_editor/utils/resource";
import { registry } from "@web/core/registry";
import { WEBSITE_BACKGROUND_OPTIONS } from "@website/builder/option_sequence";

export class DiligenceStyleOption extends BaseOptionComponent {
    static template = "theme_diligence_next.DiligenceStyleOption";
    static selector = [
        "main .oe_structure > section",
        "main #wrap > section",
        ".card",
        ".s_card",
        ".o_wslides_course_card",
        ".oe_product_cart",
    ].join(", ");
}

class DiligenceStyleOptionPlugin extends Plugin {
    static id = "DiligenceStyleOption";
    resources = {
        builder_options: [
            withSequence(after(WEBSITE_BACKGROUND_OPTIONS), DiligenceStyleOption),
        ],
    };
}

registry.category("website-plugins").add(
    DiligenceStyleOptionPlugin.id,
    DiligenceStyleOptionPlugin
);
