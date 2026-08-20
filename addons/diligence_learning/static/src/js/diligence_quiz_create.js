import { patch } from '@web/core/utils/patch';
import QuestionFormWidget from '@website_slides/js/slides_course_quiz_question_form';

function selectedType(widget) {
    return widget.$('.diligence-question-type').val() || 'single_choice';
}

function updateAnswerInputs(widget, type) {
    const answerLines = widget.$('.o_wslides_js_quiz_answer');
    const answerList = widget.$('.o_wslides_js_quiz_answer').first().parent();
    const isText = ['short_answer', 'essay'].includes(type);
    answerList.toggleClass('d-none', isText);
    answerLines.find('.o_wslides_js_quiz_is_correct input').each(function () {
        this.type = type === 'multiple_choice' ? 'checkbox' : 'radio';
    });
    if (type === 'true_false' && answerLines.length >= 2) {
        const values = ['True', 'False'];
        answerLines.each(function (index) {
            $(this).find('.o_wslides_js_quiz_answer_value').val(values[index]);
        });
    }
}

patch(QuestionFormWidget.prototype, {
    async start() {
        const result = await super.start(...arguments);
        const type = this.question.question_type || 'single_choice';
        this.$('.diligence-question-type').val(type);
        updateAnswerInputs(this, type);
        this.$('.diligence-question-type').on('change.diligenceQuiz', (event) => {
            updateAnswerInputs(this, event.currentTarget.value);
        });
        return result;
    },

    _serializeForm($form) {
        const type = selectedType(this);
        const answers = [];
        let sequence = 1;
        if (!['short_answer', 'essay'].includes(type)) {
            $form.find('.o_wslides_js_quiz_answer').each(function () {
                const value = $(this).find('.o_wslides_js_quiz_answer_value').val();
                if (value.trim()) {
                    answers.push({
                        sequence: sequence++,
                        text_value: value,
                        is_correct: $(this).find('input[type=radio], input[type=checkbox]').prop('checked') === true,
                        comment: $(this).find('.o_wslides_js_quiz_answer_comment input[type=text]').val().trim(),
                    });
                }
            });
        }
        return {
            existing_question_id: this.$el.data('id'),
            sequence: this.sequence,
            question: $form.find('.o_wslides_quiz_question input[type=text]').val(),
            question_type: type,
            slide_id: this.slideId,
            answer_ids: answers,
        };
    },
});
