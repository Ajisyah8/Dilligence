from odoo import api, models, Command


class SlideChannelMandarinContent(models.Model):
    _inherit = 'slide.channel'

    @api.model
    def configure_mandarin_quiz_types(self):
        """Give the six active Mandarin quizzes different native question types."""
        course = self.search([('name', '=', 'Mandarin Video Course')], limit=1)
        quizzes = course.slide_ids.filtered(
            lambda slide: slide.active and slide.slide_category == 'quiz'
        ).sorted('sequence')
        if len(quizzes) < 6:
            return False

        audio_slide = course.slide_ids.filtered(
            lambda slide: slide.active and slide.slide_category == 'audio' and slide.binary_content
        )[:1]
        configurations = [
            {
                'type': 'single_choice',
                'question': 'Pilih pinyin dengan nada yang benar untuk 妈 (ibu).',
                'answers': [('mā', True), ('má', False), ('mǎ', False), ('mà', False)],
            },
            {
                'type': 'multiple_choice',
                'question': 'Pilih semua ungkapan yang dapat digunakan untuk menyapa orang.',
                'answers': [('你好 (nǐ hǎo)', True), ('早安 (zǎo ān)', True), ('谢谢 (xièxie)', False), ('晚上好 (wǎnshàng hǎo)', True)],
            },
            {
                'type': 'true_false',
                'question': 'Bahasa Mandarin memiliki empat nada utama.',
                'answers': [('Benar', True), ('Salah', False)],
            },
            {
                'type': 'short_answer',
                'question': 'Tuliskan pinyin dari 你好.',
                'variants': 'ni hao\nnǐ hǎo',
            },
            {
                'type': 'essay',
                'question': 'Jelaskan cara memperkenalkan nama dan asal Anda dalam bahasa Mandarin.',
                'rubric': 'Nilai ketepatan struktur: 我叫..., 我是..., dan pelafalan/pinyin yang relevan.',
            },
            {
                'type': 'listening',
                'question': 'Dengarkan audio, lalu pilih ungkapan yang terdengar.',
                'answers': [('你好 (nǐ hǎo)', True), ('谢谢 (xièxie)', False), ('再见 (zàijiàn)', False)],
                'audio_file': audio_slide.binary_content if audio_slide else False,
                'audio_filename': 'mandarin-listening-question.mp3',
            },
        ]

        for quiz, config in zip(quizzes[:6], configurations):
            question = quiz.question_ids[:1]
            if question:
                question = question[0]
            else:
                question = self.env['slide.question'].create({'slide_id': quiz.id})
            values = {
                'question': config['question'],
                'question_type': config['type'],
                'required': True,
                'weight': 1.0,
                'allow_partial_score': config['type'] == 'multiple_choice',
                'short_answer_variants': config.get('variants', False),
                'grading_rubric': config.get('rubric', False),
                'listening_answer_type': 'choice',
                'audio_file': config.get('audio_file', False),
                'audio_filename': config.get('audio_filename', False),
                'feedback_after_submit': True,
            }
            question.write(values)
            question.answer_ids.unlink()
            if config.get('answers'):
                self.env['slide.answer'].create([
                    {'question_id': question.id, 'text_value': text, 'is_correct': correct}
                    for text, correct in config['answers']
                ])
        return True

    @api.model
    def add_mandarin_quiz_questions(self):
        """Add one extra practice question to every active Mandarin quiz.

        The marker in the question text makes this safe to run repeatedly
        during local setup or module upgrades.
        """
        course = self.search([('name', '=', 'Mandarin Video Course')], limit=1)
        quizzes = course.slide_ids.filtered(
            lambda slide: slide.active and slide.is_published and slide.slide_category == 'quiz'
        ).sorted('sequence')
        if not quizzes:
            return 0

        audio_slide = course.slide_ids.filtered(
            lambda slide: slide.active and slide.slide_category == 'audio' and slide.binary_content
        )[:1]
        extra_configs = [
            {
                'question_type': 'true_false',
                'question': '[Diligence Extra] Mandarin memiliki empat nada utama.',
                'answers': [('Benar', True), ('Salah', False)],
            },
            {
                'question_type': 'multiple_choice',
                'question': '[Diligence Extra] Pilih semua sapaan Mandarin yang benar.',
                'answers': [('ni hao', True), ('zao an', True), ('xie xie', False), ('zai jian', True)],
            },
            {
                'question_type': 'short_answer',
                'question': '[Diligence Extra] Tuliskan pinyin untuk "terima kasih".',
                'variants': 'xie xie\nxiexie',
            },
            {
                'question_type': 'essay',
                'question': '[Diligence Extra] Tulis dua kalimat untuk memperkenalkan diri.',
                'rubric': 'Periksa struktur kalimat, kosakata, dan penggunaan pinyin/hanzi.',
            },
            {
                'question_type': 'listening',
                'question': '[Diligence Extra] Dengarkan audio lalu pilih ungkapan yang terdengar.',
                'answers': [('ni hao', True), ('xie xie', False), ('zai jian', False)],
                'audio_file': audio_slide.binary_content if audio_slide else False,
                'audio_filename': 'mandarin-extra-listening.mp3',
            },
            {
                'question_type': 'single_choice',
                'question': '[Diligence Extra] Pilih arti kata "ni hao".',
                'answers': [('Halo', True), ('Selamat malam', False), ('Terima kasih', False)],
            },
        ]
        created = 0
        for index, quiz in enumerate(quizzes):
            if quiz.question_ids.filtered(lambda question: question.question.startswith('[Diligence Extra]')):
                continue
            config = extra_configs[index % len(extra_configs)]
            values = {
                'slide_id': quiz.id,
                'sequence': max(quiz.question_ids.mapped('sequence') or [0]) + 1,
                'question': config['question'],
                'question_type': config['question_type'],
                'required': True,
                'weight': 1.0,
                'allow_partial_score': config['question_type'] == 'multiple_choice',
                'short_answer_variants': config.get('variants', False),
                'grading_rubric': config.get('rubric', False),
                'listening_answer_type': 'choice',
                'audio_file': config.get('audio_file', False),
                'audio_filename': config.get('audio_filename', False),
                'feedback_after_submit': True,
            }
            if config.get('answers'):
                # Create all options together so Odoo's native quiz constraint
                # sees both a correct and an incorrect answer immediately.
                values['answer_ids'] = [
                    Command.create({
                        'sequence': answer_index,
                        'text_value': text,
                        'is_correct': correct,
                    })
                    for answer_index, (text, correct) in enumerate(config['answers'], start=1)
                ]
            question = self.env['slide.question'].create(values)
            created += 1
        return created

    @api.model
    def add_section_one_lesson_three_quiz(self):
        """Add an idempotent multi-type practice quiz after Section 01 lesson 3."""
        course = self.search([('name', '=', 'Mandarin Video Course')], limit=1)
        if not course:
            return False
        section_slides = self.env['slide.slide'].search([
            ('channel_id', '=', course.id),
            ('category_id.name', '=', 'Section 01 - Pinyin and Tones'),
            ('active', '=', True),
        ], order='sequence, id')
        video = section_slides.filtered(
            lambda slide: slide.name.startswith('Video Lesson 03 -')
        )[:1]
        if not video:
            return False

        marker = 'Quiz Lesson 03 - Four Tones in Context'
        existing = self.env['slide.slide'].search([
            ('channel_id', '=', course.id),
            ('name', '=', marker),
        ], limit=1)
        if existing:
            return existing

        following = section_slides.filtered(lambda slide: slide.sequence > video.sequence)
        for slide in following.sorted('sequence', reverse=True):
            slide.write({'sequence': slide.sequence + 1})

        audio_slide = section_slides.filtered(
            lambda slide: slide.slide_category == 'audio' and slide.binary_content
        )[:1]
        quiz = self.env['slide.slide'].create({
            'name': marker,
            'slide_category': 'quiz',
            'channel_id': course.id,
            'category_id': video.category_id.id,
            'sequence': video.sequence + 1,
            'description': 'Latihan penguatan empat nada Mandarin setelah Video Lesson 03.',
            'is_published': True,
            'active': True,
            'quiz_passing_score': 70.0,
            # Zero means unlimited attempts. Students may repeat practice
            # quizzes as often as needed without losing their attempt history.
            'quiz_max_attempts': 0,
            'quiz_randomize_answers': True,
        })
        questions = [
            {
                'question': 'Nada ke-berapa yang memiliki pola suara tinggi dan datar?',
                'question_type': 'single_choice',
                'answers': [('Nada pertama', True), ('Nada kedua', False), ('Nada ketiga', False), ('Nada keempat', False)],
            },
            {
                'question': 'Pilih semua contoh suku kata dengan nada keempat.',
                'question_type': 'multiple_choice',
                'allow_partial_score': True,
                'answers': [('mà', True), ('mā', False), ('mǎ', False), ('màn', True)],
            },
            {
                'question': 'Benar atau salah: nada ketiga biasanya memiliki pola turun lalu naik.',
                'question_type': 'true_false',
                'answers': [('Benar', True), ('Salah', False)],
            },
            {
                'question': 'Tuliskan pinyin bernada untuk kata "ibu" dalam bahasa Mandarin.',
                'question_type': 'short_answer',
                'short_answer_variants': 'mā\nma',
            },
            {
                'question': 'Jelaskan dengan singkat perbedaan nada kedua dan nada ketiga.',
                'question_type': 'essay',
                'grading_rubric': 'Nilai pemahaman pola naik pada nada kedua dan pola turun-naik pada nada ketiga.',
            },
            {
                'question': 'Dengarkan audio lalu pilih pinyin yang paling sesuai dengan bunyi yang terdengar.',
                'question_type': 'listening',
                'listening_answer_type': 'choice',
                'audio_file': audio_slide.binary_content if audio_slide else False,
                'audio_filename': 'lesson-03-four-tones-listening.mp3',
                'answers': [('mā', True), ('má', False), ('mǎ', False), ('mà', False)],
            },
        ]
        for sequence, config in enumerate(questions, start=1):
            values = {
                'slide_id': quiz.id,
                'sequence': sequence,
                'question': config['question'],
                'question_type': config['question_type'],
                'required': True,
                'weight': 1.0,
                'allow_partial_score': config.get('allow_partial_score', False),
                'short_answer_variants': config.get('short_answer_variants', False),
                'listening_answer_type': config.get('listening_answer_type', 'choice'),
                'audio_file': config.get('audio_file', False),
                'audio_filename': config.get('audio_filename', False),
                'grading_rubric': config.get('grading_rubric', False),
                'feedback_after_submit': True,
            }
            if config.get('answers'):
                values['answer_ids'] = [
                    Command.create({
                        'sequence': answer_sequence,
                        'text_value': text,
                        'is_correct': correct,
                    })
                    for answer_sequence, (text, correct) in enumerate(config['answers'], start=1)
                ]
            self.env['slide.question'].create(values)
        return quiz

    @api.model
    def attach_lesson_three_quiz_to_video(self):
        """Show the Lesson 03 practice questions below the Lesson 03 video."""
        course = self.search([('name', '=', 'Mandarin Video Course')], limit=1)
        if not course:
            return False
        video = course.slide_ids.filtered(
            lambda slide: slide.active and slide.name.startswith('Video Lesson 03 -')
        )[:1]
        quiz = course.slide_ids.filtered(
            lambda slide: slide.name == 'Quiz Lesson 03 - Four Tones in Context'
        )[:1]
        if not video or not quiz:
            return False
        if not video.question_ids:
            quiz.question_ids.write({'slide_id': video.id})
        quiz.write({'active': False, 'is_published': False})
        video.write({
            'quiz_passing_score': quiz.quiz_passing_score,
            'quiz_max_attempts': quiz.quiz_max_attempts,
            'quiz_randomize_answers': quiz.quiz_randomize_answers,
        })
        return video

    @api.model
    def rebuild_mandarin_video_course_content(self):
        """Organise the existing Mandarin demo materials into six learning sections.

        This is intentionally idempotent: it updates the existing records instead
        of creating duplicate courses or lessons. Original binary files are not
        generated here; they remain available for upload through the course editor.
        """
        course = self.search([('name', '=', 'Mandarin Video Course')], limit=1)
        if not course:
            return False

        section_names = [
            ('Section 01 - Pinyin and Tones', 'Master pinyin, the four tones, and clear Mandarin pronunciation.'),
            ('Section 02 - Greetings and Introductions', 'Build simple sentences for greetings, names, countries, and numbers.'),
            ('Section 03 - Time and Daily Routine', 'Talk about dates, time, schedules, and everyday activities.'),
            ('Section 04 - Family, Food, and Shopping', 'Use practical vocabulary for family, meals, prices, and shopping.'),
            ('Section 05 - Directions and Travel', 'Handle directions, transport, locations, and common travel situations.'),
            ('Section 06 - Conversation and Review', 'Combine the foundations in practical conversations and review tests.'),
        ]
        lesson_topics = [
            ('Pinyin and initials', 'Learn the Mandarin sound system and common initials.'),
            ('Finals and tone pairs', 'Practise finals and distinguish tone combinations.'),
            ('Four tones in context', 'Listen to and repeat the four tones in useful words.'),
            ('Pronunciation correction', 'Review common pronunciation mistakes and mouth position.'),
            ('Pinyin dictation review', 'Write pinyin after listening to short syllables.'),
            ('Greetings and polite expressions', 'Say hello, goodbye, thank you, and sorry naturally.'),
            ('Introducing yourself', 'Introduce your name, origin, and language ability.'),
            ('Pronouns and basic sentences', 'Use 我, 你, 他, 她 and simple 是 sentences.'),
            ('Numbers and phone numbers', 'Read numbers and exchange contact details.'),
            ('Introduction review', 'Review greetings, introductions, pronouns, and numbers.'),
            ('Days, dates, and months', 'Say the day, date, month, and year.'),
            ('Telling the time', 'Ask and answer questions about time and schedules.'),
            ('Daily activities', 'Describe a simple daily routine using common verbs.'),
            ('Making appointments', 'Arrange a meeting and confirm a time.'),
            ('Time and routine review', 'Review dates, time, routines, and appointments.'),
            ('Family members', 'Talk about family members and relationships.'),
            ('Food and drinks', 'Order food and drinks using polite expressions.'),
            ('Likes and dislikes', 'Express preferences with 喜欢 and 不喜欢.'),
            ('Prices and shopping', 'Ask prices, quantities, and negotiate a simple purchase.'),
            ('Family and shopping review', 'Review family, food, preferences, and shopping.'),
            ('Locations and position words', 'Use 在 and position words to describe locations.'),
            ('Asking for directions', 'Ask for and give simple directions.'),
            ('Transport and tickets', 'Use Mandarin at stations and when buying tickets.'),
            ('Hotel and travel needs', 'Handle basic hotel and travel conversations.'),
            ('Directions and travel review', 'Review travel vocabulary and practical dialogues.'),
            ('Useful conversation patterns', 'Connect short sentences into a natural exchange.'),
            ('Listening for key words', 'Identify important words in short Mandarin dialogues.'),
            ('Reading short dialogues', 'Read simple dialogues with pinyin and characters.'),
            ('Integrated practice', 'Combine pronunciation, vocabulary, and conversation skills.'),
            ('Final review and answer key', 'Complete a final review and check the answer key.'),
        ]

        sections = course.slide_ids.filtered('is_category').sorted('sequence')
        lessons = course.slide_ids.filtered(lambda slide: not slide.is_category).sorted('sequence')
        if len(sections) < 6 or len(lessons) < 30:
            return False

        # Keep exactly six visible sections. Extra legacy sections are archived,
        # not deleted, so existing progress and attachments remain recoverable.
        for index, section in enumerate(sections[:6]):
            name, description = section_names[index]
            section.write({
                'name': name,
                'description': description,
                'sequence': index * 6 + 1,
                'is_published': True,
                'active': True,
            })
        sections[6:].write({'active': False, 'is_published': False})

        lesson_types = ['document', 'audio', 'video', 'quiz', 'audio']
        for index, lesson in enumerate(lessons[:30]):
            section_index = index // 5
            topic, detail = lesson_topics[index]
            lesson_type = lesson_types[index % 5]
            section = sections[section_index]
            prefix = {
                'document': 'PDF',
                'audio': 'Audio Listening' if index % 5 == 1 else 'Audio Dictation',
                'video': 'Video Lesson',
                'quiz': 'Quiz and Answer Key',
            }[lesson_type]
            lesson.write({
                'name': '%s %02d - %s' % (prefix, index + 1, topic),
                'description': detail,
                'category_id': section.id,
                'sequence': section_index * 6 + (index % 5) + 2,
                'is_published': True,
                'active': True,
            })

            if lesson_type == 'quiz':
                question_text = 'Apa hal utama yang dipelajari pada materi "%s"?' % topic
                question = lesson.question_ids[:1]
                if question:
                    question = question[0]
                    question.write({
                        'question': question_text,
                        'question_type': 'single_choice',
                        'required': True,
                        'weight': 1.0,
                    })
                    question.answer_ids.unlink()
                else:
                    question = self.env['slide.question'].create({
                        'slide_id': lesson.id,
                        'question': question_text,
                        'question_type': 'single_choice',
                        'required': True,
                        'weight': 1.0,
                    })
                answers = [
                    ('Materi %s' % topic, True),
                    ('Materi pelajaran berikutnya', False),
                    ('Materi yang tidak berkaitan', False),
                    ('Tidak ada jawaban yang benar', False),
                ]
                self.env['slide.answer'].create([
                    {'question_id': question.id, 'text_value': text, 'is_correct': correct}
                    for text, correct in answers
                ])

        # The old 30-section seed created 150 lessons. Keep only the first
        # 30 lessons in the six-section learning path; archive the remaining
        # legacy lessons so course counters and progress use visible content.
        lessons[30:].write({'active': False, 'is_published': False})

        return True
