# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io

from openpyxl import Workbook

from odoo.addons.website_slides.tests.common import SlidesCase
from odoo.tests.common import users


class TestCertificationImport(SlidesCase):
    @users('user_manager')
    def test_import_certification_questions_from_xlsx(self):
        survey = self.env['survey.survey'].create({
            'title': 'Certification Import',
            'certification': True,
            'scoring_type': 'scoring_with_answers',
        })

        workbook = Workbook()
        sheet = workbook.active
        sheet.append([
            'Section', 'Title', 'Question Type', 'Mandatory',
            'Answer 1', 'Correct 1', 'Score 1',
            'Answer 2', 'Correct 2', 'Score 2',
            'Correct Value', 'Score',
        ])
        sheet.append(['Basics', 'What can fly?', 'simple_choice', 'TRUE', 'Bird', 'TRUE', 1, 'Elephant', 'FALSE', 0, '', ''])
        sheet.append(['Basics', 'How many continents are there?', 'numerical_box', 'TRUE', '', '', '', '', '', '', 7, 2])

        buffer = io.BytesIO()
        workbook.save(buffer)

        created_questions = survey.import_certification_questions_from_xlsx(buffer.getvalue())

        self.assertEqual(len(created_questions), 3)
        self.assertEqual(survey.question_and_page_ids.filtered('is_page').mapped('title'), ['Basics'])
        self.assertEqual(survey.question_ids[0].question_type, 'simple_choice')
        self.assertEqual(len(survey.question_ids[0].suggested_answer_ids), 2)
        self.assertEqual(survey.question_ids[1].question_type, 'numerical_box')
        self.assertEqual(survey.question_ids[1].answer_numerical_box, 7)
