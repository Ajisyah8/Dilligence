from odoo import SUPERUSER_ID, api, Command


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    channel = env.ref('diligence_learning.course_diligence_business_mandarin', raise_if_not_found=False)
    if not channel or env['slide.slide'].search_count([('name', '=', 'Dummy Quiz - Business Mandarin Foundations'), ('channel_id', '=', channel.id)]):
        return

    slide = env['slide.slide'].create({
        'name': 'Dummy Quiz - Business Mandarin Foundations',
        'slide_category': 'quiz',
        'channel_id': channel.id,
        'is_published': True,
        'sequence': 10,
        'quiz_passing_score': 70,
        'quiz_max_attempts': 3,
    })
    questions = [
        {
            'question': 'What does 你好 (nǐ hǎo) mean?',
            'question_type': 'single_choice', 'weight': 1,
            'answers': [('Hello', True, 'Correct. 你好 is a common greeting.'), ('Thank you', False, ''), ('Goodbye', False, '')],
        },
        {
            'question': 'Which phrases are appropriate in a business meeting?',
            'question_type': 'multiple_choice', 'allow_partial_score': True, 'weight': 2,
            'answers': [('请坐 (Please sit)', True, ''), ('谢谢 (Thank you)', True, ''), ('晚安 (Good night)', False, '')],
        },
        {
            'question': '商务 (shāngwù) means business.',
            'question_type': 'true_false', 'weight': 1,
            'answers': [('True', True, ''), ('False', False, '')],
        },
        {
            'question': 'Type the pinyin for “thank you”.',
            'question_type': 'short_answer', 'weight': 2,
            'short_answer_variants': 'xiexie\n谢谢',
            'answers': [('Accepted text answer', True, ''), ('Other answer', False, '')],
        },
        {
            'question': 'Write two Mandarin sentences introducing yourself in a professional context.',
            'question_type': 'essay', 'weight': 3,
            'grading_rubric': 'Give full marks when the answer contains two understandable Mandarin sentences, a self-introduction, and appropriate professional vocabulary.',
            'answers': [('Manual grading required', True, ''), ('Manual grading required', False, '')],
        },
        {
            'question': 'Listening practice: choose the phrase that means “See you tomorrow”. Upload the audio file before publishing the real lesson.',
            'question_type': 'listening', 'listening_answer_type': 'choice', 'weight': 1,
            'answers': [('明天见 (míngtiān jiàn)', True, ''), ('昨天见 (zuótiān jiàn)', False, '')],
        },
    ]
    for sequence, values in enumerate(questions, start=1):
        answer_commands = [Command.create({
            'text_value': text, 'is_correct': correct, 'comment': comment, 'sequence': index,
        }) for index, (text, correct, comment) in enumerate(values.pop('answers'), start=1)]
        values.update({'slide_id': slide.id, 'sequence': sequence, 'answer_ids': answer_commands})
        env['slide.question'].create(values)
