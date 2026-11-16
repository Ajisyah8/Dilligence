from odoo import Command
from odoo.tests.common import TransactionCase


class TestDiligencePlacementTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course_a = cls.env['slide.channel'].create({'name': 'Placement course A'})
        cls.course_b = cls.env['slide.channel'].create({'name': 'Placement course B'})
        cls.survey = cls.env['survey.survey'].create({
            'title': 'Placement test scoring test',
            'diligence_is_placement_test': True,
            'diligence_placement_course_ids': [
                Command.create({'course_id': cls.course_a.id, 'min_score': 70}),
                Command.create({'course_id': cls.course_b.id, 'min_score': 70}),
            ],
        })
        cls.course_a_config, cls.course_b_config = cls.survey.diligence_placement_course_ids
        cls.question_a = cls.env['survey.question'].create({
            'survey_id': cls.survey.id,
            'title': 'Question for course A',
            'question_type': 'simple_choice',
            'is_scored_question': True,
            'answer_score': 1,
            'diligence_placement_course_id': cls.course_a_config.id,
            'suggested_answer_ids': [
                Command.create({'value': 'Correct', 'is_correct': True, 'answer_score': 1}),
                Command.create({'value': 'Incorrect', 'is_correct': False, 'answer_score': 0}),
            ],
        })
        cls.question_b = cls.env['survey.question'].create({
            'survey_id': cls.survey.id,
            'title': 'Question for course B',
            'question_type': 'char_box',
            'diligence_placement_course_id': cls.course_b_config.id,
        })

    def test_course_recommendations_and_manual_short_answer_review(self):
        answer = self.question_a.suggested_answer_ids.filtered('is_correct')
        user_input = self.env['survey.user_input'].create({
            'survey_id': self.survey.id,
            'predefined_question_ids': [Command.set([self.question_a.id, self.question_b.id])],
            'user_input_line_ids': [
                Command.create({
                    'question_id': self.question_a.id,
                    'answer_type': 'suggestion',
                    'suggested_answer_id': answer.id,
                }),
                Command.create({
                    'question_id': self.question_b.id,
                    'answer_type': 'char_box',
                    'value_char_box': 'Student answer requiring instructor review',
                }),
            ],
        })

        user_input.write({'state': 'done'})

        results = user_input.diligence_placement_course_result_ids
        result_a = results.filtered(lambda result: result.course_id == self.course_a)
        result_b = results.filtered(lambda result: result.course_id == self.course_b)
        self.assertEqual(result_a.outcome, 'pass')
        self.assertEqual(result_a.score, 100)
        self.assertEqual(result_b.outcome, 'manual')
        self.assertEqual(result_b.manually_graded_count, 1)

        result_b.manual_decision = 'review'
        self.assertEqual(result_b.final_recommendation, 'review')

    def test_unselected_course_questions_are_not_marked_as_passed(self):
        user_input = self.env['survey.user_input'].create({
            'survey_id': self.survey.id,
            'predefined_question_ids': [Command.set([self.question_a.id])],
        })
        user_input.write({'state': 'done'})

        result_b = user_input.diligence_placement_course_result_ids.filtered(
            lambda result: result.course_id == self.course_b
        )
        self.assertEqual(result_b.outcome, 'not_tested')
