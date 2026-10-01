"""Russian messages for shared validation and service errors."""

RUSSIAN = {'Authorization failed': 'Неверная электронная почта или пароль',
 'Name is required.': 'Укажите имя.',
 'Email is required.': 'Укажите электронную почту.',
 'Password is required.': 'Укажите пароль.',
 'Password must be at least 8 characters.': 'Пароль должен содержать не менее 8 символов.',
 'Please select at least one role.': 'Выберите хотя бы одну роль.',
 'Invalid role selected': 'Выбрана недопустимая роль.',
 'A user with this email already exists.': 'Пользователь с такой электронной почтой уже '
                                           'существует.',
 'Login required': 'Необходимо войти в систему.',
 'Access denied': 'Доступ запрещен.',
 'User does not have this role': 'У пользователя нет этой роли.',
 'Teacher is not assigned to this course': 'Преподаватель не назначен на эту дисциплину.',
 "Teacher is not assigned to this draft's course": 'Преподаватель не назначен на дисциплину этого '
                                                   'черновика.',
 'Draft not found': 'Черновик не найден.',
 'Course not found': 'Дисциплина не найдена.',
 'Uploaded file is empty': 'Загруженный файл пуст.',
 'Filename is too long': 'Название файла слишком длинное.',
 'Uploaded file exceeds the 5 MiB limit': 'Размер файла превышает 5 МиБ.',
 'Could not read file as UTF-8 text': 'Не удалось прочитать файл как текст UTF-8.',
 'Unsupported file type. Only .txt and .md are supported in the prototype.': 'В прототипе '
                                                                             'поддерживаются '
                                                                             'только файлы .txt и '
                                                                             '.md.',
 'Cannot generate draft: course has no uploaded materials': 'Для создания черновика необходимо '
                                                            'загрузить материалы дисциплины.',
 'Cannot mark feedback as given before writing feedback.': 'Сначала сохраните замечания, затем '
                                                           'верните черновик преподавателю.'}

def translate(message):
    if message in RUSSIAN:
        return RUSSIAN[message]
    if message.startswith("This action requires role "):
        return "Для этого действия необходимо выбрать соответствующую роль."
    if "status" in message.lower():
        return "Это действие недоступно при текущем статусе черновика."
    return message
