/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SlideCategoryListRenderer } from "@website_slides/slide_category_list_renderer";

patch(SlideCategoryListRenderer.prototype, {
    getSectionColumns(columns) {
        const handles = columns.filter((column) => column.widget === "handle");
        const buttons = columns.filter((column) => column.type === "button_group");
        const title = columns.find(
            (column) => column.type === "field" && column.name === this.titleField
        );
        const titleColspan = columns.length - handles.length - buttons.length;
        return [...handles, { ...title, colspan: titleColspan }, ...buttons];
    },
});
