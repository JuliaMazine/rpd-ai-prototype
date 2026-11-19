"""Account forms and the active role must agree throughout navigation."""
import pytest

from app.auth import hash_password
from app.constants import ROLE_METHODIST, ROLE_TEACHER
from app.models import User


def test_login_modes_show_one_form(client):
    login = client.get('/login')
    assert 'action="/login"' in login.text
    assert 'action="/register"' not in login.text
    registration = client.get('/login?mode=register')
    assert 'action="/register"' in registration.text
    assert 'action="/login"' not in registration.text


def test_registration_error_preserves_details_but_not_password(client):
    response = client.post('/register', data={
        'name': 'Анна', 'email': 'anna@example.com', 'password': 'short',
        'roles': [ROLE_METHODIST],
    })
    assert response.status_code == 400
    assert response.context['mode'] == 'register'
    assert response.context['name'] == 'Анна'
    assert response.context['email'] == 'anna@example.com'
    assert response.context['selected_roles'] == [ROLE_METHODIST]
    assert 'short' not in response.text
    assert 'role="alert"' in response.text


def test_multi_role_registration_selection_switching_and_logout(client):
    response = client.post('/register', data={
        'name': 'Both roles', 'email': 'both@example.com', 'password': 'password123',
        'roles': [ROLE_TEACHER, ROLE_METHODIST],
    }, follow_redirects=False)
    assert response.headers['location'] == '/select-role'
    assert client.get('/dashboard', follow_redirects=False).headers['location'] == '/select-role'
    assert client.get('/select-role').context['roles'] == [ROLE_TEACHER, ROLE_METHODIST]

    client.post('/select-role', data={'role': ROLE_METHODIST})
    dashboard = client.get('/dashboard')
    assert dashboard.context['active_role'] == ROLE_METHODIST
    assert 'data-role="USER_METHODIST"' in dashboard.text
    assert 'href="/select-role"' in dashboard.text
    chooser = client.get('/select-role')
    assert chooser.context['ui_role'] == ROLE_METHODIST
    client.post('/select-role', data={'role': ROLE_TEACHER})
    assert client.get('/dashboard').context['active_role'] == ROLE_TEACHER
    client.get('/logout')
    assert client.get('/select-role', follow_redirects=False).headers['location'] == '/login'


def test_duplicate_registration_roles_use_single_role_shortcut(client):
    response = client.post('/register', data={
        'name': 'Teacher', 'email': 'teacher@example.com', 'password': 'password123',
        'roles': [ROLE_TEACHER, ROLE_TEACHER],
    }, follow_redirects=False)
    assert response.headers['location'] == '/dashboard'
    assert client.get('/dashboard').context['active_role'] == ROLE_TEACHER


@pytest.mark.parametrize('url', ['/select-role', '/switch-role?role=USER_METHODIST'])
def test_unassigned_role_is_rejected(authenticated_client, url):
    if url == '/select-role':
        response = authenticated_client.post(url, data={'role': ROLE_METHODIST})
    else:
        response = authenticated_client.get(url)
    assert response.status_code == 403
    assert authenticated_client.get('/dashboard').context['active_role'] == ROLE_TEACHER


def test_no_role_account_has_an_actionable_empty_state(client, db_session):
    db_session.add(User(name='No roles', email='none@example.com', password_hash=hash_password('password123')))
    db_session.commit()
    client.post('/login', data={'email': 'none@example.com', 'password': 'password123'})
    response = client.get('/select-role')
    assert 'пока нет доступных ролей' in response.text
    assert 'action="/select-role"' not in response.text
    assert 'href="/logout"' in response.text


def test_user_creation_error_preserves_form(authenticated_client):
    response = authenticated_client.post('/admin/users', data={
        'name': 'Новый пользователь', 'email': 'new@example.com',
        'password': 'short', 'roles': [ROLE_TEACHER, ROLE_METHODIST],
    })
    assert response.status_code == 400
    assert response.context['form_name'] == 'Новый пользователь'
    assert response.context['form_email'] == 'new@example.com'
    assert response.context['selected_roles'] == [ROLE_TEACHER, ROLE_METHODIST]
    assert 'short' not in response.text
