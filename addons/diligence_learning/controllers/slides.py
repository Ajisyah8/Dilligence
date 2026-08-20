import base64
import werkzeug

from odoo import http, fields, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import html_escape
from odoo.addons.website_slides.controllers.main import WebsiteSlides
from odoo.http import request


class DiligenceWebsiteSlides(WebsiteSlides):
    def _get_channel_progress(self, channel, include_quiz=False):
        """Include completion records for publishers/admins in the sidebar."""
        progress = super()._get_channel_progress(channel, include_quiz=include_quiz)
        if request.env.user._is_public() or not (
                request.env.user._is_admin() or channel.can_publish):
            return progress

        slides = request.env['slide.slide'].sudo().search([
            ('channel_id', '=', channel.id),
        ])
        partners = request.env['slide.slide.partner'].sudo().search([
            ('channel_id', '=', channel.id),
            ('partner_id', '=', request.env.user.partner_id.id),
            ('slide_id', 'in', slides.ids),
        ])
        for partner in partners:
            progress.setdefault(partner.slide_id.id, {}).update(partner.read()[0])
        return progress

    def _diligence_mark_completed(self, slide):
        """Mark a non-quiz lesson complete without invoking quiz karma rules."""
        uncompleted = slide.filtered(lambda item: not item.user_has_completed)
        partner = request.env.user.partner_id
        membership_model = request.env['slide.slide.partner'].sudo()
        existing = membership_model.search([
            ('slide_id', 'in', uncompleted.ids),
            ('partner_id', '=', partner.id),
        ])
        existing.write({'completed': True})
        new_slides = uncompleted.sudo() - existing.mapped('slide_id')
        membership_model.create([{
            'slide_id': item.id,
            'channel_id': item.channel_id.id,
            'partner_id': partner.id,
            'vote': 0,
            'completed': True,
        } for item in new_slides])

    @http.route(
        '/slides/slide/<model("slide.slide"):slide>/set_completed',
        website=True, type='http', auth='user',
    )
    def diligence_native_slide_set_completed(self, slide, next_slide_id=None, **kwargs):
        """Keep the native LMS URL while allowing authorized publishers.

        Odoo's native endpoint requires a student membership.  Administrators
        and course publishers need the same action while validating content.
        The URL remains the standard Odoo URL so the lesson navigation stays
        compatible with the existing frontend.
        """
        if not slide.active:
            raise werkzeug.exceptions.NotFound()
        if slide.slide_category == 'quiz' or slide.question_ids:
            raise werkzeug.exceptions.Forbidden()
        if not (
                request.env.user._is_admin()
                or slide.channel_id.is_member
                or slide.channel_id.can_publish):
            raise werkzeug.exceptions.Forbidden()

        self._diligence_mark_completed(slide)
        next_slide = False
        if next_slide_id:
            try:
                next_slide = request.env['slide.slide'].browse(int(next_slide_id)).exists()
            except (TypeError, ValueError):
                next_slide = False
            if next_slide and next_slide.channel_id != slide.channel_id:
                next_slide = False
        target = next_slide or slide
        return request.redirect('/slides/slide/%s' % request.env['ir.http']._slug(target))

    @http.route('/diligence/slides/media/<int:slide_id>', type='http', auth='public', website=True)
    def diligence_slide_media(self, slide_id, **kwargs):
        """Serve lesson media for the custom Diligence preview.

        The route deliberately keeps the access check in the custom module so
        the new preview does not depend on Odoo's embedded lesson viewer.
        """
        # ``auth='public'`` keeps the iframe usable when the browser does not
        # forward the parent page's auth challenge.  Re-apply the logged-in
        # Odoo user to the recordset so access is still enforced server-side.
        # Public users may not have read ACLs on slide records, so use sudo
        # only for loading the binary after the route has identified the
        # record.  The access decision below is still evaluated as the
        # current request user.
        slide = request.env['slide.slide'].sudo().browse(slide_id).exists()
        if not slide or not slide.active:
            raise werkzeug.exceptions.NotFound()

        # The preview is rendered inside the authenticated lesson page.  Do
        # not use ``can_access_from_current_website`` as the first gate here:
        # it depends on the website request context and can incorrectly reject
        # a valid lesson when the channel has no explicit website assigned.
        current_user = slide.env.user
        is_admin = current_user._is_admin()
        is_officer = current_user.has_group('website_slides.group_website_slides_officer')
        user_slide = slide.with_user(current_user)
        is_publisher = user_slide.channel_id.can_publish
        is_member = user_slide.channel_id.is_member
        if not (is_admin or is_officer or is_publisher or is_member or slide.is_preview):
            raise werkzeug.exceptions.Forbidden()

        if slide.slide_category == 'document' and slide.document_binary_content:
            content = base64.b64decode(slide.document_binary_content)
            content_type = 'application/pdf'
            filename = '%s.pdf' % slide.name
        elif slide.slide_category in ('audio', 'video') and slide.source_type == 'local_file' and slide.binary_content:
            content = base64.b64decode(slide.binary_content)
            content_type = 'audio/mpeg' if slide.slide_category == 'audio' else 'video/mp4'
            filename = slide.name
        else:
            raise werkzeug.exceptions.NotFound()

        return request.make_response(content, headers=[
            ('Content-Type', content_type),
            ('Content-Length', str(len(content))),
            ('Content-Disposition', 'inline; filename="%s"' % filename.replace('"', '')),
            ('X-Content-Type-Options', 'nosniff'),
        ])

    @http.route('/diligence/slides/description/<int:slide_id>', type='http', auth='user', website=True)
    def diligence_slide_description(self, slide_id, **kwargs):
        """Return the editable lesson description for the fullscreen reader."""
        slide = request.env['slide.slide'].browse(slide_id).exists()
        if not slide or not slide.active:
            raise werkzeug.exceptions.NotFound()
        if not (request.env.user._is_admin() or slide.channel_id.can_publish or slide.channel_id.is_member):
            raise werkzeug.exceptions.Forbidden()
        description = slide.description or (
            '<p>Pelajari materi <strong>%s</strong> secara bertahap melalui preview di atas.</p>'
            % html_escape(slide.name)
        )
        return request.make_json_response({'description': description})

    @http.route(
        '/diligence/slides/slide/<int:slide_id>/set_completed',
        type='http', auth='user', website=True,
    )
    def diligence_slide_set_completed(self, slide_id, next_slide_id=None, **kwargs):
        """Mark a lesson complete for a learner or an authorised course manager.

        Odoo's standard self-mark route intentionally requires membership.  A
        course manager/admin may still need to preview and validate lessons,
        so this route permits publishers while keeping the normal student
        membership and lesson-type checks intact.
        """
        slide = request.env['slide.slide'].browse(slide_id).exists()
        if not slide or not slide.active:
            raise werkzeug.exceptions.NotFound()
        if not (slide.env.user._is_admin() or slide.channel_id.is_member or slide.channel_id.can_publish):
            raise werkzeug.exceptions.Forbidden()
        if slide.slide_category == 'quiz' or slide.question_ids:
            raise werkzeug.exceptions.Forbidden()

        self._diligence_mark_completed(slide)

        next_slide = False
        if next_slide_id:
            try:
                next_slide = request.env['slide.slide'].browse(int(next_slide_id)).exists()
            except (TypeError, ValueError):
                next_slide = False
            if next_slide and next_slide.channel_id != slide.channel_id:
                next_slide = False
        target = next_slide or slide
        return request.redirect('/slides/slide/%s' % request.env['ir.http']._slug(target))

    @http.route('/slides/slide/quiz/question_add_or_update', type='jsonrpc', methods=['POST'], auth='user', website=True)
    def slide_quiz_question_add_or_update(self, slide_id, question, sequence, answer_ids,
                                           existing_question_id=None, question_type='single_choice'):
        """Extend Odoo's quick quiz editor with Diligence question types."""
        allowed_types = {
            'single_choice', 'multiple_choice', 'true_false', 'short_answer', 'essay', 'listening',
        }
        if question_type not in allowed_types:
            question_type = 'single_choice'
        answer_values = [(0, 0, {
            'sequence': answer.get('sequence', index + 1),
            'text_value': answer.get('text_value', ''),
            'is_correct': bool(answer.get('is_correct')),
            'comment': answer.get('comment', ''),
        }) for index, answer in enumerate(answer_ids or []) if answer.get('text_value', '').strip()]
        new_question_values = {
            'sequence': sequence,
            'question': question,
            'slide_id': slide_id,
            'question_type': question_type,
            'answer_ids': answer_values,
        }
        try:
            slide_question = request.env['slide.question'].new(new_question_values)
            slide_question._validate_fields(new_question_values.keys())
        except ValidationError as error:
            return {'error': error.args[0]}
        fetch_res = self._fetch_slide(slide_id)
        if fetch_res.get('error'):
            return fetch_res
        slide = fetch_res['slide']
        if existing_question_id:
            request.env['slide.question'].search([
                ('slide_id', '=', slide.id), ('id', '=', int(existing_question_id)),
            ]).unlink()
        request.env['slide.slide.partner'].search([
            ('slide_id', '=', slide_id), ('partner_id', '=', request.env.user.partner_id.id),
        ]).write({'completed': False})
        slide_question = request.env['slide.question'].create(new_question_values)
        return request.env['ir.qweb']._render('website_slides.lesson_content_quiz_question', {
            'slide': slide,
            'question': slide_question,
        })
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
        auto_question_count = 0
        correct_question_count = 0
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

            if not is_manual:
                auto_question_count += 1
                if is_correct:
                    correct_question_count += 1

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
                # These values are returned only after submission, so the
                # correct answer is never exposed while the quiz is open.
                'selected_answer_ids': selected.ids,
                'correct_answer_ids': question.answer_ids.filtered('is_correct').ids,
                'selected_answers': selected.mapped('text_value') or ([text_answer] if text_answer else []),
                'answer_key': (
                    [line for line in (question.short_answer_variants or '').splitlines() if line.strip()]
                    if question.question_type == 'short_answer' or (
                        question.question_type == 'listening'
                        and question.listening_answer_type == 'short_answer'
                    )
                    else question.answer_ids.filtered('is_correct').mapped('text_value')
                ),
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
            'autoQuestionCount': auto_question_count,
            'correctQuestionCount': correct_question_count,
            'quizAttemptsCount': existing_count + 1,
            'maxAttempts': slide.quiz_max_attempts,
            'attemptsRemaining': max(0, slide.quiz_max_attempts - existing_count - 1)
                if slide.quiz_max_attempts else -1,
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
