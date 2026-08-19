import { rpc } from '@web/core/network/rpc';

function quizStorageKey(root) {
    return `diligence.quiz.${root.dataset.id}`;
}

function isMultiTypeRoot(root) {
    return root?.dataset.diligenceMultitype === '1';
}

function enhanceFullscreenQuiz(root) {
    if (!root || root.dataset.diligenceEnhanced) return;
    const questions = root.querySelectorAll('.o_wslides_js_lesson_quiz_question[data-question-type]');
    const customQuestions = [...questions].filter((question) => question.dataset.questionType !== 'single_choice');
    if (!customQuestions.length) return;
    root.classList.add('o_diligence_multitype_quiz');
    root.dataset.diligenceMultitype = '1';
    root.dataset.diligenceEnhanced = '1';
    customQuestions.forEach((question) => {
        const type = question.dataset.questionType;
        const existing = question.querySelector('.list-group');
        const answers = [...question.querySelectorAll('a.o_wslides_quiz_answer')].map((answer) => ({
            id: answer.dataset.answerId,
            text: answer.dataset.text || answer.textContent.trim(),
        }));
        const group = document.createElement('div');
        group.className = 'o_diligence_quiz_answer_group list-group';
        if (type === 'listening' && question.dataset.audioUrl) {
            const audio = document.createElement('audio');
            audio.controls = true;
            audio.preload = 'metadata';
            audio.src = question.dataset.audioUrl;
            audio.className = 'w-100 mb-3';
            group.appendChild(audio);
        }
        if (type === 'short_answer' || type === 'essay' || (type === 'listening' && !answers.length)) {
            const field = document.createElement(type === 'essay' ? 'textarea' : 'input');
            field.className = 'form-control o_diligence_quiz_text_answer mb-3';
            field.dataset.questionId = question.dataset.questionId;
            if (type === 'essay') field.rows = 5;
            group.appendChild(field);
        } else {
            answers.forEach((answer) => {
                const label = document.createElement('label');
                label.className = 'o_diligence_quiz_choice list-group-item d-flex align-items-center gap-2';
                const input = document.createElement('input');
                input.type = type === 'multiple_choice' ? 'checkbox' : 'radio';
                input.name = `diligence_question_${question.dataset.questionId}`;
                input.value = answer.id;
                input.className = 'o_diligence_quiz_choice_input';
                input.dataset.questionId = question.dataset.questionId;
                label.append(input, document.createTextNode(answer.text));
                group.appendChild(label);
            });
        }
        existing?.replaceWith(group);
    });
    restoreAnswers(root);
}

function collectAnswers(root) {
    const answers = {};
    root.querySelectorAll('.o_wslides_js_lesson_quiz_question').forEach((question) => {
        const questionId = question.dataset.questionId;
        answers[questionId] = { answer_ids: [], text_answer: '' };
        question.querySelectorAll('input[type=radio]:checked, input[type=checkbox]:checked').forEach((field) => {
            answers[questionId].answer_ids.push(Number(field.value));
        });
        const text = question.querySelector('.o_diligence_quiz_text_answer');
        if (text) {
            answers[questionId].text_answer = text.value;
        }
    });
    return answers;
}

function restoreAnswers(root) {
    try {
        const answers = JSON.parse(localStorage.getItem(quizStorageKey(root)) || '{}');
        Object.entries(answers).forEach(([questionId, value]) => {
            const question = root.querySelector(`.o_wslides_js_lesson_quiz_question[data-question-id="${questionId}"]`);
            if (!question) return;
            question.querySelectorAll('input[type=radio], input[type=checkbox]').forEach((field) => {
                field.checked = (value.answer_ids || []).includes(Number(field.value));
            });
            const text = question.querySelector('.o_diligence_quiz_text_answer');
            if (text) text.value = value.text_answer || '';
        });
    } catch {
        // A corrupt local draft must never prevent the quiz from opening.
    }
}

function showResult(root, result) {
    root.querySelectorAll('.o_diligence_quiz_choice_input, .o_diligence_quiz_text_answer').forEach((field) => {
        field.disabled = true;
    });
    const button = root.querySelector('.o_wslides_js_lesson_quiz_submit');
    if (button) {
        button.disabled = true;
        button.textContent = result.pending_review ? 'Waiting for teacher grading' : 'Submitted';
    }
    const validation = root.querySelector('.o_wslides_js_lesson_quiz_validation');
    if (validation) {
        validation.classList.remove('d-none');
        validation.innerHTML = `<div class="alert ${result.pending_review ? 'alert-info' : (result.status === 'passed' ? 'alert-success' : 'alert-warning')}">${result.pending_review ? 'Your answer is waiting for teacher grading.' : `Quiz submitted. Score: ${Number(result.score || 0).toFixed(1)}%`}</div>`;
    }
    localStorage.removeItem(quizStorageKey(root));
}

document.addEventListener('input', (event) => {
    const root = event.target.closest?.('.o_diligence_multitype_quiz');
    if (isMultiTypeRoot(root)) {
        localStorage.setItem(quizStorageKey(root), JSON.stringify(collectAnswers(root)));
    }
}, true);

document.addEventListener('change', (event) => {
    const root = event.target.closest?.('.o_diligence_multitype_quiz');
    if (isMultiTypeRoot(root)) {
        localStorage.setItem(quizStorageKey(root), JSON.stringify(collectAnswers(root)));
    }
}, true);

document.addEventListener('click', async (event) => {
    const button = event.target.closest?.('.o_wslides_js_lesson_quiz_submit');
    const root = button?.closest('.o_diligence_multitype_quiz');
    if (!isMultiTypeRoot(root)) {
        return;
    }
    event.preventDefault();
    event.stopImmediatePropagation();
    const answers = collectAnswers(root);
    const requiredQuestions = [...root.querySelectorAll('.o_wslides_js_lesson_quiz_question[data-required="True"], .o_wslides_js_lesson_quiz_question[data-required="true"]')];
    if (requiredQuestions.some((question) => {
        const hasChoice = question.querySelector('input[type=radio]:checked, input[type=checkbox]:checked');
        const text = question.querySelector('.o_diligence_quiz_text_answer');
        return !hasChoice && !(text && text.value.trim());
    })) {
        return;
    }
    button.disabled = true;
    try {
        const result = await rpc('/slides/slide/quiz/submit', {
            slide_id: Number(root.dataset.id),
            answers,
        });
        if (result.error) {
            button.disabled = false;
            return;
        }
        showResult(root, result);
    } catch {
        button.disabled = false;
    }
}, true);

document.querySelectorAll('.o_diligence_multitype_quiz').forEach(restoreAnswers);

const fullscreenObserver = new MutationObserver(() => {
    document.querySelectorAll('.o_diligence_fs_quiz').forEach(enhanceFullscreenQuiz);
});
fullscreenObserver.observe(document.body, { childList: true, subtree: true });
document.querySelectorAll('.o_diligence_fs_quiz').forEach(enhanceFullscreenQuiz);
