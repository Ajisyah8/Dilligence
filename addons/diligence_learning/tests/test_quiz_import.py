import io
import base64

import xlsxwriter
from openpyxl import load_workbook

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestDiligenceQuizImport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env['slide.channel'].create({'name': 'Bulk quiz import test'})
        cls.slide = cls.env['slide.slide'].create({
            'name': 'Imported quiz',
            'channel_id': cls.channel.id,
            'slide_category': 'quiz',
        })

    def _xlsx(self, headers, rows):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet()
        worksheet.write_row(0, 0, headers)
        for row_index, row in enumerate(rows, start=1):
            worksheet.write_row(row_index, 0, row)
        workbook.close()
        return output.getvalue()

    def test_imports_supported_question_types(self):
        headers = [
            'Question', 'Question Type', 'Weight', 'Required', 'Allow Partial Score',
            'Listening Answer Type', 'Accepted Answers', 'Grading Rubric',
            'Answer 1', 'Correct 1', 'Answer 2', 'Correct 2',
        ]
        rows = [
            ['Pick one', 'single_choice', 1, 'TRUE', 'FALSE', '', '', '', 'A', 'TRUE', 'B', 'FALSE'],
            ['Pick all', 'multiple_choice', 2, 'TRUE', 'TRUE', '', '', '', 'A', 'TRUE', 'B', 'FALSE'],
            ['True false', 'true_false', 1, 'TRUE', 'FALSE', '', '', '', 'True', 'TRUE', 'False', 'FALSE'],
            ['Short answer', 'short_answer', 1, 'TRUE', 'FALSE', '', 'yes|yeah', '', '', '', '', ''],
            ['Essay', 'essay', 3, 'TRUE', 'FALSE', '', '', 'Assess clarity.', '', '', '', ''],
            ['Listen choice', 'listening', 1, 'TRUE', 'FALSE', 'choice', '', '', 'A', 'TRUE', 'B', 'FALSE'],
            ['Listen text', 'listening', 1, 'TRUE', 'FALSE', 'short_answer', 'hello|hi', '', '', '', '', ''],
        ]
        values = self.env['slide.question']._prepare_questions_from_xlsx(
            self.slide, self._xlsx(headers, rows),
        )

        self.assertEqual([item['question_type'] for item in values], [
            'single_choice', 'multiple_choice', 'true_false', 'short_answer',
            'essay', 'listening', 'listening',
        ])
        self.assertEqual(values[3]['short_answer_variants'], 'yes\nyeah')
        self.assertEqual(values[4]['grading_rubric'], 'Assess clarity.')
        self.assertEqual(values[5]['listening_answer_type'], 'choice')
        self.assertEqual(values[6]['listening_answer_type'], 'short_answer')

    def test_legacy_template_still_imports_as_single_choice(self):
        headers = ['Question', 'Answer 1', 'Correct 1', 'Answer 2', 'Correct 2']
        rows = [['Legacy question', 'Correct', 'TRUE', 'Incorrect', 'FALSE']]
        values = self.env['slide.question']._prepare_questions_from_xlsx(
            self.slide, self._xlsx(headers, rows),
        )
        self.assertEqual(values[0]['question_type'], 'single_choice')

    def test_short_answer_requires_accepted_answer(self):
        headers = ['Question', 'Question Type']
        rows = [['Missing key', 'short_answer']]
        with self.assertRaises(ValidationError):
            self.env['slide.question']._prepare_questions_from_xlsx(
                self.slide, self._xlsx(headers, rows),
            )

    def test_backend_wizard_imports_all_supported_types_and_preserves_existing(self):
        existing = self.env['slide.question'].create({
            'slide_id': self.slide.id,
            'question': 'Existing question',
            'sequence': 4,
            'question_type': 'short_answer',
            'short_answer_variants': 'previous answer',
        })
        headers = [
            'Question', 'Question Type', 'Weight', 'Required', 'Allow Partial Score',
            'Listening Answer Type', 'Accepted Answers', 'Grading Rubric',
            'Answer 1', 'Correct 1', 'Comment 1', 'Answer 2', 'Correct 2', 'Comment 2',
            'Answer 3', 'Correct 3', 'Comment 3', 'Answer 4', 'Correct 4', 'Comment 4',
        ]

        def question_row(title, question_type, **values):
            row = [title, question_type, 1, 'TRUE', 'FALSE', '', '', ''] + [''] * 12
            for column, value in values.items():
                row[headers.index(column)] = value
            return row

        rows = [
            question_row('Single choice sample', 'single_choice',
                         **{'Answer 1': 'Correct option', 'Correct 1': 'TRUE',
                            'Answer 2': 'Wrong option', 'Correct 2': 'FALSE'}),
            question_row('Multiple choice sample', 'multiple_choice',
                         **{'Allow Partial Score': 'TRUE', 'Answer 1': 'Correct A', 'Correct 1': 'TRUE',
                            'Answer 2': 'Correct B', 'Correct 2': 'TRUE',
                            'Answer 3': 'Wrong option', 'Correct 3': 'FALSE'}),
            question_row('True false sample', 'true_false',
                         **{'Answer 1': 'True', 'Correct 1': 'TRUE',
                            'Answer 2': 'False', 'Correct 2': 'FALSE'}),
            question_row('Short answer sample', 'short_answer',
                         **{'Accepted Answers': 'yes|yeah'}),
            question_row('Essay sample', 'essay',
                         **{'Grading Rubric': 'Assess clarity and accuracy.'}),
            question_row('Listening choice sample', 'listening',
                         **{'Listening Answer Type': 'choice', 'Answer 1': 'Heard word', 'Correct 1': 'TRUE',
                            'Answer 2': 'Distractor', 'Correct 2': 'FALSE'}),
            question_row('Listening short answer sample', 'listening',
                         **{'Listening Answer Type': 'short_answer', 'Accepted Answers': 'hello|hi'}),
        ]
        content = self._xlsx(headers, rows)
        wizard = self.env['diligence.quiz.import.wizard'].create({
            'slide_id': self.slide.id,
            'file_data': base64.b64encode(content),
            'file_name': 'questions.xlsx',
        })

        action = wizard.action_import()

        imported = self.slide.question_ids - existing
        imported = imported.sorted('sequence')
        self.assertEqual(action['type'], 'ir.actions.act_window_close')
        self.assertEqual(len(imported), 7)
        self.assertEqual(imported.mapped('question_type'), [
            'single_choice', 'multiple_choice', 'true_false', 'short_answer',
            'essay', 'listening', 'listening',
        ])
        self.assertEqual(imported[3].short_answer_variants, 'yes\nyeah')
        self.assertEqual(imported[4].grading_rubric, 'Assess clarity and accuracy.')
        self.assertEqual(imported[5].listening_answer_type, 'choice')
        self.assertEqual(imported[6].listening_answer_type, 'short_answer')
        self.assertEqual(len(imported[0].answer_ids), 2)
        self.assertEqual(sum(imported[1].answer_ids.mapped('is_correct')), 2)
        self.assertTrue(imported[2].answer_ids.filtered('is_correct'))
        self.assertEqual(existing.question, 'Existing question')
        self.assertTrue(all(question.sequence > existing.sequence for question in imported))

    def test_media_slide_can_import_and_export_attached_quiz(self):
        video = self.env['slide.slide'].create({
            'name': 'Lesson video with quiz',
            'channel_id': self.channel.id,
            'slide_category': 'video',
        })
        headers = [
            'Question', 'Question Type', 'Weight', 'Required', 'Allow Partial Score',
            'Listening Answer Type', 'Accepted Answers', 'Grading Rubric',
            'Answer 1', 'Correct 1', 'Comment 1', 'Answer 2', 'Correct 2', 'Comment 2',
            'Feedback After Submit',
        ]
        rows = [[
            'Listen and identify the word', 'listening', 2, 'TRUE', 'FALSE', 'choice', '', '',
            '你好', 'TRUE', 'Correct', '再见', 'FALSE', '', 'FALSE',
        ]]
        wizard = self.env['diligence.quiz.import.wizard'].create({
            'slide_id': video.id,
            'file_data': base64.b64encode(self._xlsx(headers, rows)),
            'file_name': 'video_quiz.xlsx',
        })
        wizard.action_import()

        question = video.question_ids
        self.assertEqual(len(question), 1)
        self.assertEqual(question.question_type, 'listening')
        self.assertEqual(question.listening_answer_type, 'choice')
        self.assertFalse(question.feedback_after_submit)

        exported = load_workbook(io.BytesIO(video._build_quiz_questions_xlsx()), data_only=True)
        sheet = exported['Quiz Questions']
        self.assertEqual(sheet['A2'].value, 'Listen and identify the word')
        self.assertEqual(sheet['B2'].value, 'listening')
        self.assertEqual(sheet['I2'].value, '你好')
        self.assertEqual(sheet['J2'].value, 'TRUE')
        self.assertEqual(sheet['U2'].value, 'FALSE')

    def test_number_only_prompts_get_a_useful_audio_fallback(self):
        question = self.env['slide.question'].create({
            'slide_id': self.slide.id,
            'question': '1.',
            'question_type': 'short_answer',
            'sequence': 1,
            'short_answer_variants': 'ni hao',
        })
        audio_slide = self.env['slide.slide'].create({
            'name': 'Audio exercise',
            'channel_id': self.channel.id,
            'slide_category': 'audio',
        })
        self.assertEqual(
            question._diligence_display_question(audio_slide, 1),
            'Listen to the audio and enter your answer for item 1.',
        )
        self.assertEqual(
            question._diligence_display_question(self.slide, 1),
            'Enter your answer for item 1.',
        )

    def test_legacy_short_answer_keys_in_answer_lines_are_graded_and_exported(self):
        question = self.env['slide.question'].create({
            'slide_id': self.slide.id,
            'question': 'Ini adalah apa? =',
            'question_type': 'short_answer',
            'sequence': 1,
            'answer_ids': [
                (0, 0, {'sequence': 1, 'text_value': 'Zhe shi shen me?', 'is_correct': True}),
                (0, 0, {'sequence': 2, 'text_value': 'zhe shi shen me', 'is_correct': True}),
            ],
        })

        self.assertEqual(question._diligence_display_question(self.slide, 1), 'Ini adalah apa?')
        self.assertTrue(question._diligence_short_answer_is_correct('zhe shi shen me'))
        workbook = load_workbook(io.BytesIO(self.slide._build_quiz_questions_xlsx()), data_only=True)
        self.assertEqual(workbook['Quiz Questions']['G2'].value, 'Zhe shi shen me?|zhe shi shen me')
