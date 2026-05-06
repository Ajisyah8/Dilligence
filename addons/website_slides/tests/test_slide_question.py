# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import io

from odoo import Command
from odoo.exceptions import ValidationError

from odoo.addons.website_slides.tests import common as slides_common
from odoo.tests.common import users

from openpyxl import Workbook

class TestSlideQuestionManagement(slides_common.SlidesCase):

    @users('user_officer')
    def test_compute_answers_validation_error(self):
        channel = self.env['slide.channel'].create({
            'name': 'Test compute answers channel',
            'slide_ids': [Command.create({
                'name': "Test compute answers validation error slide",
                'slide_category': 'quiz',
                'question_ids': [Command.create({
                    'question': 'Will test compute answers validation error pass?',
                    'answer_ids': [
                        Command.create({
                            'text_value': 'An incorrect answer',
                        }),
                        Command.create({
                            'is_correct': True,
                            'text_value': 'A correct answer',
                        })
                    ]
                })]
            })]
        })

        question = channel.slide_ids[0].question_ids[0]
        self.assertFalse(question.answers_validation_error)

        for val in (False, True):
            question.answer_ids[0].is_correct = val
            question.answer_ids[1].is_correct = val
            self.assertTrue(question.answers_validation_error)

    @users('user_officer')
    def test_prepare_questions_from_xlsx(self):
        slide = self.env['slide.slide'].create({
            'name': 'Quiz import target',
            'channel_id': self.channel.id,
            'slide_category': 'quiz',
        })
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(['Question', 'Answer 1', 'Correct 1', 'Comment 1', 'Answer 2', 'Correct 2', 'Comment 2'])
        sheet.append([
            'What flies?',
            'Bird', 'TRUE', 'Correct, birds can fly.',
            'Elephant', 'FALSE', 'Elephants cannot fly.',
        ])

        buffer = io.BytesIO()
        workbook.save(buffer)
        prepared_questions = self.env['slide.question']._prepare_questions_from_xlsx(slide, buffer.getvalue())

        self.assertEqual(len(prepared_questions), 1)
        self.assertEqual(prepared_questions[0]['question'], 'What flies?')
        self.assertEqual(len(prepared_questions[0]['answer_ids']), 2)
        self.assertTrue(prepared_questions[0]['answer_ids'][0]['is_correct'])
        self.assertFalse(prepared_questions[0]['answer_ids'][1]['is_correct'])

    @users('user_officer')
    def test_prepare_questions_from_xlsx_requires_mixed_answers(self):
        slide = self.env['slide.slide'].create({
            'name': 'Quiz import validation target',
            'channel_id': self.channel.id,
            'slide_category': 'quiz',
        })
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(['Question', 'Answer 1', 'Correct 1', 'Answer 2', 'Correct 2'])
        sheet.append(['Invalid question', 'Choice A', 'TRUE', 'Choice B', 'TRUE'])

        buffer = io.BytesIO()
        workbook.save(buffer)

        with self.assertRaises(ValidationError):
            self.env['slide.question']._prepare_questions_from_xlsx(slide, buffer.getvalue())
