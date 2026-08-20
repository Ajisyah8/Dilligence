import { rpc } from '@web/core/network/rpc';

function escapeHtml(value) {
    const element = document.createElement('div');
    element.textContent = value === undefined || value === null ? '' : String(value);
    return element.innerHTML;
}

function quizStorageKey(root) {
    return `diligence.quiz.${root.dataset.id}`;
}

function readQuizState(root) {
    try {
        const stored = JSON.parse(localStorage.getItem(quizStorageKey(root)) || '{}');
        return stored.answers ? stored : {answers: stored, submitted: false, result: null};
    } catch {
        return {answers: {}, submitted: false, result: null};
    }
}

function writeQuizState(root, answers, submitted = false, result = null) {
    localStorage.setItem(quizStorageKey(root), JSON.stringify({answers, submitted, result}));
}

function isMultiTypeRoot(root) {
    return root?.dataset.diligenceMultitype === '1';
}

function enhanceFullscreenQuiz(root) {
    if (!root) return;
    if (root.dataset.diligenceEnhanced) {
        maintainQuizControls(root);
        return;
    }
    const questions = root.querySelectorAll('.o_wslides_js_lesson_quiz_question[data-question-type]');
    const customQuestions = [...questions].filter((question) => question.dataset.questionType !== 'single_choice');
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
    const state = restoreAnswers(root);
    if (state.submitted && state.result) {
        showResult(root, state.result);
    } else if (root.querySelector('.completed-disabled')) {
        showCompletedNativeAnswerKeys(root);
    }
}

function ensureRetrySubmitButton(root) {
    const validation = root.querySelector('.o_wslides_js_lesson_quiz_validation');
    if (!validation) return;
    validation.classList.remove('d-none', 'bg-100', 'border-bottom');
    validation.classList.add('diligence-quiz-retry-validation');
    if (validation.querySelector('.o_wslides_js_lesson_quiz_submit')) return;
    validation.innerHTML = `
        <div class="d-flex flex-wrap align-items-center gap-3">
            <button type="button" class="btn btn-primary text-uppercase fw-bold o_wslides_js_lesson_quiz_submit">
                Submit answers
            </button>
            <div class="d-none text-danger o_wslides_js_quiz_submit_error">
                <i class="fa fa-close me-1"></i>
                <span class="o_wslides_js_quiz_submit_error_text"></span>
            </div>
        </div>
    `;
}

function maintainQuizControls(root) {
    if (root.dataset.diligenceRetryMode === '1') {
        ensureRetrySubmitButton(root);
        return;
    }
    const state = readQuizState(root);
    if (state.submitted && state.result) {
        const validation = root.querySelector('.o_wslides_js_lesson_quiz_validation');
        if (validation && validation.dataset.diligenceResultRendered !== '1') {
            showResult(root, state.result);
        }
    } else if (root.querySelector('.completed-disabled')) {
        showCompletedNativeAnswerKeys(root);
    }
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
    const state = readQuizState(root);
    Object.entries(state.answers || {}).forEach(([questionId, value]) => {
        const question = root.querySelector(`.o_wslides_js_lesson_quiz_question[data-question-id="${questionId}"]`);
        if (!question) return;
        question.querySelectorAll('input[type=radio], input[type=checkbox]').forEach((field) => {
            field.checked = (value.answer_ids || []).includes(Number(field.value));
        });
        const text = question.querySelector('.o_diligence_quiz_text_answer');
        if (text) text.value = value.text_answer || '';
    });
    return state;
}

function showResult(root, result) {
    const answers = result.answers || {};
    root.querySelectorAll('input[type=radio], input[type=checkbox], .o_diligence_quiz_text_answer').forEach((field) => {
        field.disabled = true;
    });
    root.querySelectorAll('.o_wslides_js_lesson_quiz_question').forEach((question) => {
        const resultData = answers[question.dataset.questionId];
        if (!resultData) return;
        question.classList.remove('o_diligence_question-correct', 'o_diligence_question-incorrect');
        question.classList.add(resultData.is_correct ? 'o_diligence_question-correct' : 'o_diligence_question-incorrect');
        const choices = [...question.querySelectorAll('.o_diligence_quiz_choice, a.o_wslides_quiz_answer')];
        const choiceDetails = choices.map((choice) => {
            const input = choice.querySelector('input');
            if (!input) return null;
            const answerId = Number(input.value);
            choice.querySelector('.o_diligence_answer-status')?.remove();
            const isCorrectAnswer = (resultData.correct_answer_ids || []).includes(answerId);
            const isSelectedAnswer = (resultData.selected_answer_ids || []).includes(answerId);
            if ((resultData.correct_answer_ids || []).includes(answerId)) {
                choice.classList.add('o_diligence_answer-correct');
            }
            if ((resultData.selected_answer_ids || []).includes(answerId)) {
                choice.classList.add('o_diligence_answer-selected');
            }
            if (isCorrectAnswer || isSelectedAnswer) {
                const status = document.createElement('span');
                status.className = `o_diligence_answer-status ms-auto ${isCorrectAnswer ? 'is-correct' : 'is-incorrect'}`;
                status.textContent = isCorrectAnswer && isSelectedAnswer
                    ? 'Your answer · Correct'
                    : isCorrectAnswer
                        ? 'Correct answer'
                        : 'Your answer · Incorrect';
                choice.appendChild(status);
            }
            const textNode = choice.querySelector('span:not(.o_diligence_answer-status)');
            return {
                id: answerId,
                text: (textNode || choice).textContent.trim(),
            };
        });
        const validChoiceDetails = choiceDetails.filter(Boolean);
        let key = question.querySelector('.o_diligence_answer-key');
        if (!key) {
            key = document.createElement('div');
            key.className = 'o_diligence_answer-key alert alert-success mt-3 mb-0';
            question.appendChild(key);
        }
        const keys = (resultData.answer_key || []).length
            ? resultData.answer_key
            : validChoiceDetails
                .filter((choice) => (resultData.correct_answer_ids || []).includes(choice.id))
                .map((choice) => choice.text);
        const selectedAnswers = (resultData.selected_answers || []).length
            ? resultData.selected_answers
            : validChoiceDetails
                .filter((choice) => (resultData.selected_answer_ids || []).includes(choice.id))
                .map((choice) => choice.text);
        const textAnswer = question.querySelector('.o_diligence_quiz_text_answer')?.value?.trim();
        if (!selectedAnswers.length && textAnswer) selectedAnswers.push(textAnswer);
        const statusLabel = resultData.is_correct ? 'Correct' : (keys.length ? 'Incorrect' : 'Waiting for teacher review');
        key.classList.toggle('alert-success', Boolean(resultData.is_correct));
        key.classList.toggle('alert-danger', !resultData.is_correct && keys.length > 0);
        key.classList.toggle('alert-info', !keys.length);
        key.innerHTML = `
            <div class="o_diligence_answer-key-status mb-2"><strong>${escapeHtml(statusLabel)}</strong></div>
            <div><strong>Your answer:</strong> ${escapeHtml(selectedAnswers.join(', ') || 'No answer')}</div>
            <div><strong>Correct answer:</strong> ${escapeHtml(keys.join(', ') || 'Requires teacher review')}</div>
        `;
    });
    const button = root.querySelector('.o_wslides_js_lesson_quiz_submit');
    if (button) {
        button.disabled = true;
        button.textContent = result.pending_review ? 'Waiting for teacher grading' : 'Submitted';
    }
    const validation = root.querySelector('.o_wslides_js_lesson_quiz_validation');
    if (validation) {
        validation.classList.remove('d-none', 'bg-100', 'border-bottom');
        validation.dataset.diligenceResultRendered = '1';
        const score = Number(result.score || 0).toFixed(1);
        const scoreBreakdown = result.autoQuestionCount
            ? ` (${result.correctQuestionCount || 0} of ${result.autoQuestionCount} automatically graded questions correct)`
            : '';
        const message = result.pending_review
            ? `Automatic score: ${score}%${scoreBreakdown}. Essay/audio answers are waiting for teacher grading.`
            : `Quiz submitted. Score: ${score}%${scoreBreakdown}`;
        const canRetry = result.attemptsRemaining === undefined
            || result.attemptsRemaining === -1
            || result.attemptsRemaining > 0;
        const retryInfo = result.attemptsRemaining === undefined || result.attemptsRemaining === -1
            ? ''
            : ` <span class="small">(${result.attemptsRemaining} attempt(s) remaining)</span>`;
        validation.innerHTML = `
            <div class="alert ${result.pending_review ? 'alert-info' : (result.status === 'passed' ? 'alert-success' : 'alert-warning')} mb-2">${message}</div>
            ${canRetry ? `<button type="button" class="btn btn-outline-primary o_diligence_quiz_retry">Try Again</button>${retryInfo}` : '<div class="small text-muted">Maximum attempts reached.</div>'}
        `;
    }
    writeQuizState(root, collectAnswers(root), true, result);
}

function resetQuizForRetry(root) {
    localStorage.removeItem(quizStorageKey(root));
    root.dataset.diligenceRetryMode = '1';
    root.querySelectorAll('.o_wslides_js_lesson_quiz_question').forEach((question) => {
        question.classList.remove('completed-disabled');
    });
    root.querySelectorAll('input[type=radio], input[type=checkbox]').forEach((field) => {
        field.disabled = false;
        field.checked = false;
    });
    root.querySelectorAll('.o_diligence_quiz_text_answer').forEach((field) => {
        field.disabled = false;
        field.value = '';
    });
    root.querySelectorAll('.o_diligence_answer-correct, .o_diligence_answer-selected').forEach((choice) => {
        choice.classList.remove('o_diligence_answer-correct', 'o_diligence_answer-selected');
    });
    root.querySelectorAll('.o_diligence_question-correct, .o_diligence_question-incorrect').forEach((question) => {
        question.classList.remove('o_diligence_question-correct', 'o_diligence_question-incorrect');
    });
    root.querySelectorAll('.o_diligence_answer-status').forEach((status) => status.remove());
    root.querySelectorAll('a.o_wslides_quiz_answer').forEach((choice) => {
        choice.classList.remove('list-group-item-success', 'list-group-item-danger');
        choice.querySelector('.fa-check-circle')?.classList.add('d-none');
        choice.querySelector('.fa-times-circle')?.classList.add('d-none');
        choice.querySelector('.fa-circle')?.classList.remove('d-none');
    });
    root.querySelectorAll('.o_diligence_answer-key').forEach((key) => key.remove());
    const validation = root.querySelector('.o_wslides_js_lesson_quiz_validation');
    if (validation) {
        delete validation.dataset.diligenceResultRendered;
        validation.replaceChildren();
    }
    ensureRetrySubmitButton(root);
    writeQuizState(root, {});
}

function showCompletedNativeAnswerKeys(root) {
    root.querySelectorAll('.o_wslides_js_lesson_quiz_question').forEach((question) => {
        if (question.querySelector('.o_diligence_answer-key')) return;
        const correct = question.querySelector('a.o_wslides_quiz_answer.list-group-item-success');
        if (!correct) return;
        const answerText = (correct.querySelector('span:last-child') || correct).textContent.trim();
        if (!answerText) return;
        const key = document.createElement('div');
        key.className = 'o_diligence_answer-key alert mt-3 mb-0';
        key.innerHTML = `<strong>Answer key:</strong> ${answerText}`;
        question.appendChild(key);
    });
    const validation = root.querySelector('.o_wslides_js_lesson_quiz_validation');
    if (validation && !validation.querySelector('.o_diligence_quiz_retry')) {
        validation.classList.remove('d-none', 'bg-100', 'border-bottom');
        validation.innerHTML = `
            <div class="d-flex flex-wrap align-items-center gap-3">
                <div class="alert alert-success mb-0 py-2">Quiz completed.</div>
                <button type="button" class="btn btn-outline-primary o_diligence_quiz_retry">Try Again</button>
            </div>
        `;
    }
}

document.addEventListener('input', (event) => {
    const root = event.target.closest?.('.o_diligence_multitype_quiz');
    if (isMultiTypeRoot(root)) {
        writeQuizState(root, collectAnswers(root));
    }
}, true);

document.addEventListener('change', (event) => {
    const root = event.target.closest?.('.o_diligence_multitype_quiz');
    if (isMultiTypeRoot(root)) {
        writeQuizState(root, collectAnswers(root));
    }
}, true);

document.addEventListener('click', async (event) => {
    const retryButton = event.target.closest?.('.o_diligence_quiz_retry');
    if (retryButton) {
        event.preventDefault();
        const retryRoot = retryButton.closest('.o_diligence_multitype_quiz');
        if (retryRoot) resetQuizForRetry(retryRoot);
        return;
    }
    const nativeChoice = event.target.closest?.('a.o_wslides_quiz_answer');
    const nativeChoiceRoot = nativeChoice?.closest('.o_diligence_multitype_quiz');
    if (nativeChoice && nativeChoiceRoot?.dataset.diligenceRetryMode === '1') {
        event.preventDefault();
        event.stopImmediatePropagation();
        const radio = nativeChoice.querySelector('input[type=radio]');
        if (radio && !radio.disabled) {
            const question = nativeChoice.closest('.o_wslides_js_lesson_quiz_question');
            question?.querySelectorAll('input[type=radio]').forEach((field) => {
                field.checked = field === radio;
            });
            writeQuizState(nativeChoiceRoot, collectAnswers(nativeChoiceRoot));
        }
        return;
    }
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
            const validation = root.querySelector('.o_wslides_js_lesson_quiz_validation');
            const errorText = result.error === 'quiz_attempt_limit'
                ? 'Maximum quiz attempts reached. Contact your teacher to reopen this quiz.'
                : 'The quiz could not be submitted. Please try again.';
            if (validation) {
                validation.insertAdjacentHTML('afterbegin', `<div class="alert alert-danger mb-3 o_diligence_quiz_error">${errorText}</div>`);
            }
            return;
        }
        delete root.dataset.diligenceRetryMode;
        showResult(root, result);
    } catch {
        button.disabled = false;
    }
}, true);

document.querySelectorAll('.o_diligence_multitype_quiz').forEach(restoreAnswers);

function keepFullscreenLessonListsOpen() {
}

const fullscreenObserver = new MutationObserver(() => {
    document.querySelectorAll('.o_diligence_fs_quiz').forEach(enhanceFullscreenQuiz);
    keepFullscreenLessonListsOpen();
});
fullscreenObserver.observe(document.body, { childList: true, subtree: true });
document.querySelectorAll('.o_diligence_fs_quiz').forEach(enhanceFullscreenQuiz);
keepFullscreenLessonListsOpen();
