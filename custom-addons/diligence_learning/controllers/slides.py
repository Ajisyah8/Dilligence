import base64
import werkzeug

from odoo import http, fields, _
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.website_slides.controllers.main import WebsiteSlides
from odoo.http import request


class DiligenceWebsiteSlides(WebsiteSlides):
    def _get_slide_quiz_data(self, slide):
        values = super()._get_slide_quiz_data(slide)
        questions = []
        for question in slide.question_ids:
            item = next((value for value in values['slide_questions'] if value['id'] == question.id), None)
            if not item:
                continue
            item.update({
                'sequence': question.sequence,
                'question_type': question.question_type,
                'required': question.required,
                'weight': question.weight,
                'feedback_after_submit': question.feedback_after_submit,
                'listening_answer_type': question.listening_answer_type,
                'audio_url': '/diligence/quiz/audio/%s' % question.id if question.audio_file else False,
            })
            if question.question_type in ('short_answer', 'essay') or (
                    question.question_type == 'listening' and question.listening_answer_type == 'short_answer'):
                item['answer_ids'] = []
            questions.append(item)
        values['slide_questions'] = questions
        return values

    def _diligence_quiz_payload(self, slide, answers):
        payload = answers or {}
        if isinstance(payload, list):
            payload = {str(answer_id): {'answer_ids': [answer_id]} for answer_id in payload}
        attempt_model = request.env['diligence.quiz.attempt'].sudo()
        response_model = request.env['diligence.quiz.response'].sudo()
        partner = request.env.user.partner_id.commercial_partner_id
        existing_count = attempt_model.search_count([('slide_id', '=', slide.id), ('partner_id', '=', partner.id)])
        if slide.quiz_max_attempts and existing_count >= slide.quiz_max_attempts:
            return {'error': 'quiz_attempt_limit'}
        attempt = attempt_model.create({
            'slide_id': slide.id,
            'partner_id': partner.id,
            'attempt_number': existing_count + 1,
            'passing_score': slide.quiz_passing_score,
            'started_at': fields.Datetime.now(),
        })
        total_weight = sum(slide.question_ids.mapped('weight')) or 1.0
        earned = 0.0
        pending_review = False
        result_answers = {}
        for question in slide.question_ids:
            raw = payload.get(str(question.id), payload.get(question.id, {})) or {}
            if isinstance(raw, list):
                raw = {'answer_ids': raw}
            selected_ids = [int(value) for value in raw.get('answer_ids', []) if str(value).isdigit()]
            selected = request.env['slide.answer'].sudo().search([
                ('id', 'in', selected_ids), ('question_id', '=', question.id),
            ])
            text_answer = raw.get('text_answer', '') or ''
            is_manual = question.question_type in ('essay', 'speaking')
            is_correct = False
            score_ratio = 0.0
            if question.question_type in ('single_choice', 'true_false'):
                correct_ids = set(question.answer_ids.filtered('is_correct').ids)
                is_correct = len(selected.ids) == 1 and set(selected.ids) == correct_ids
                score_ratio = 1.0 if is_correct else 0.0
            elif question.question_type in ('multiple_choice', 'listening') and (
                    question.question_type != 'listening' or question.listening_answer_type == 'choice'):
                correct_ids = set(question.answer_ids.filtered('is_correct').ids)
                selected_ids_set = set(selected.ids)
                is_correct = selected_ids_set == correct_ids
                if question.allow_partial_score and correct_ids:
                    score_ratio = max(0.0, len(selected_ids_set & correct_ids) - len(selected_ids_set - correct_ids)) / len(correct_ids)
                else:
                    score_ratio = 1.0 if is_correct else 0.0
            elif question.question_type == 'short_answer' or (
                    question.question_type == 'listening' and question.listening_answer_type == 'short_answer'):
                is_correct = question._diligence_short_answer_is_correct(text_answer)
                score_ratio = 1.0 if is_correct else 0.0
            elif is_manual:
                pending_review = True

            response = response_model.create({
                'attempt_id': attempt.id,
                'question_id': question.id,
                'selected_answer_ids': [fields.Command.set(selected.ids)],
                'text_answer': text_answer,
                'is_correct': is_correct,
                'auto_score': score_ratio * question.weight,
                'manual_score': 0.0,
            })
            earned += response.auto_score
            result_answers[question.id] = {
                'is_correct': is_correct,
                'comment': next(iter(selected.filtered('is_correct')), False).comment if selected.filtered('is_correct') else '',
            }
        attempt.write({
            'submitted_at': fields.Datetime.now(),
            'auto_score': earned / total_weight * 100,
            'state': 'pending_review' if pending_review else ('passed' if earned / total_weight * 100 >= slide.quiz_passing_score else 'failed'),
        })
        self._set_viewed_slide(slide, quiz_attempts_inc=True)
        if attempt.state == 'passed':
            slide._action_mark_completed()
        self._channel_remove_session_answers(slide.channel_id, slide)
        return {
            'answers': result_answers,
            'completed': slide.user_has_completed,
            'status': attempt.state,
            'score': attempt.final_score,
            'pending_review': pending_review,
            'quizAttemptsCount': existing_count + 1,
        }

    @http.route('/diligence/quiz/audio/<int:question_id>', type='http', auth='user', website=True)
    def diligence_quiz_audio(self, question_id, **kwargs):
        question_sudo = request.env['slide.question'].sudo().browse(question_id).exists()
        if not question_sudo or not question_sudo.audio_file:
            raise werkzeug.exceptions.NotFound()
        slide = request.env['slide.slide'].browse(question_sudo.slide_id.id).exists()
        if not slide.channel_id.is_member and not slide.is_preview:
            raise werkzeug.exceptions.Forbidden()
        return request.make_response(
            base64.b64decode(question_sudo.audio_file),
            headers=[('Content-Type', 'audio/mpeg'), ('Content-Disposition', 'inline; filename="%s"' % (question_sudo.audio_filename or 'question-audio'))],
        )

    @http.route()
    def slide_view(self, slide, **kwargs):
        # Keep Odoo's standard completion behaviour for every other course.
        if slide.channel_id.id not in (7, 8, 9):
            return super().slide_view(slide, **kwargs)

        if not slide.channel_id.can_access_from_current_website() or not slide.active:
            raise werkzeug.exceptions.NotFound()
        membership = request.env['slide.channel.partner'].sudo().search([
            ('channel_id', '=', slide.channel_id.id),
            ('partner_id', '=', request.env.user.partner_id.commercial_partner_id.id),
            ('member_status', 'in', ('joined', 'ongoing', 'completed')),
        ], limit=1)
        if membership and not membership._diligence_access_is_valid():
            raise werkzeug.exceptions.Forbidden('This course access has expired.')
        if slide.is_category:
            return request.redirect(slide.channel_id.website_absolute_url)

        # Diligence learners decide completion through media end, quiz completion,
        # or the manual circle button. Opening an article must not mark it done.
        self._set_viewed_slide(slide)
        values = self._get_slide_detail(slide)
        if slide.question_ids:
            values.update(self._get_slide_quiz_data(slide))
        values['channel_progress'] = self._get_channel_progress(slide.channel_id, include_quiz=True)
        values['category_data'] = self._prepare_collapsed_categories(values['category_data'], slide, False)
        values.update({
            'search_category': slide.category_id if kwargs.get('search_category') else None,
            'search_tag': request.env['slide.tag'].browse(int(kwargs.get('search_tag'))) if kwargs.get('search_tag') else None,
            'slide_categories': dict(request.env['slide.slide']._fields['slide_category']._description_selection(request.env)) if kwargs.get('search_slide_category') else None,
            'search_slide_category': kwargs.get('search_slide_category'),
            'search_uncategorized': kwargs.get('search_uncategorized'),
        })
        values['channel'] = slide.channel_id
        values = self._prepare_additional_channel_values(values, **kwargs)
        values['signup_allowed'] = request.env['res.users'].sudo()._get_signup_invitation_scope() == 'b2c'
        if kwargs.get('fullscreen') == '1':
            values.update(self._slide_channel_prepare_review_values(slide.channel_id))
            return request.render('website_slides.slide_fullscreen', values)
        values.pop('channel', None)
        return request.render('website_slides.slide_main', values)

    @http.route('/slides/slide/quiz/submit', type='jsonrpc', auth='public', website=True)
    def slide_quiz_submit(self, slide_id, answer_ids=None, answers=None):
        fetch_res = self._fetch_slide(slide_id)
        if fetch_res.get('error'):
            return fetch_res
        slide = fetch_res['slide']
        if answers is not None or any(question.question_type != 'single_choice' for question in slide.question_ids):
            if request.website.is_public_user():
                return {'error': 'public_user'}
            return self._diligence_quiz_payload(slide, answers if answers is not None else answer_ids)
        return super().slide_quiz_submit(slide_id, answer_ids)
