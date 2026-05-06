import { Component, useState } from "@odoo/owl";

export class SlideUploadSourceTypes extends Component {
    static props = {
        attributes: {
            type: Object,
            shape: {
                sourceTypeLabel: { type: String, optional: true },
                selectFileLabel: { type: String, optional: true },
                acceptedFiles: { type: String, optional: true },
                urlInputLabel: { type: String, optional: true },
                urlInputName: { type: String, optional: true },
            },
        },
        isLocalSource: Boolean,
        onClickSourceType: Function,
        onChangeFileInput: Function,
        onChangeUrl: Function,
    };
    static template = "website_slides.SlideUploadSourceTypes";

    setup() {
        this.state = useState({ url: "" });
    }
}
