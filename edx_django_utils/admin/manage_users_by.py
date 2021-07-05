"""
Management command `manage_user` is used to idempotently create or remove
Django users, set/unset permission bits, and associate groups by name.
"""

from logging import getLogger

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import identify_hasher, is_password_usable
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.translation import gettext as _
import sys


logger = getLogger(__name__)  # pylint: disable=invalid-name


try:
    from common.djangoapps.student.models import UserProfile
except ImportError:
    UserProfile = None

def is_valid_django_hash(encoded):
    """
    Starting with django 2.1, the function is_password_usable no longer checks whether encode
    is a valid password created by a django hasher (hasher in  PASSWORD_HASHERS setting)
    Adding this function to create constant behavior as we upgrade django versions
    """
    try:
        identify_hasher(encoded)
    except ValueError:
        return False
    return True


def _maybe_update(user, attribute, new_value):
    """
    DRY helper.  If the specified attribute of the user differs from the
    specified value, it will be updated.
    """
    old_value = getattr(user, attribute)
    if new_value != old_value:
        setattr(user, attribute, new_value)

def _check_email_match(user, email):
    """
    DRY helper.
    Requiring the user to specify both username and email will help catch
    certain issues, for example if the expected username has already been
    taken by someone else.
    """
    if user.email.lower() != email.lower():
        # The passed email address doesn't match this username's email address.
        # Assume a problem and fail.
        raise CommandError(
            _(
                'Skipping user "{}" because the specified and existing email '
                'addresses do not match.'
            ).format(user.username)
        )

def _handle_remove(username, email):  # lint-amnesty, pylint: disable=missing-function-docstring
    print(username)
    try:
        user = get_user_model().objects.get(username=username)
    except get_user_model().DoesNotExist:
        return
    _check_email_match(user, email)
    user.delete()

@transaction.atomic
def update_user(username, email, is_remove, is_staff, is_superuser, groups,  # lint-amnesty, pylint: disable=arguments-differ
           unusable_password, initial_password_hash, *args, **options):

    sys.stderr.write(_('Entering into method for : "{}"').format(username))

    if not UserProfile:
        logger.error('UserProfile module does not exist.')
        return

    if is_remove:
        return _handle_remove(username, email)

    old_groups, new_groups = set(), set()
    user, created = get_user_model().objects.get_or_create(
        username=username,
        defaults={'email': email}
    )


    if created:
        if initial_password_hash:
            if not (is_password_usable(initial_password_hash) and is_valid_django_hash(initial_password_hash)):
                raise CommandError(f'The password hash provided for user {username} is invalid.')
            user.password = initial_password_hash
        else:
            # Set the password to a random, unknown, but usable password
            # allowing self-service password resetting.  Cases where unusable
            # passwords are required, should be explicit, and will be handled below.
            user.set_password('dummypassword')
    else:
        # NOTE, we will not update the email address of an existing user.
        _check_email_match(user, email)
        old_groups = set(user.groups.all())

    _maybe_update(user, 'is_staff', is_staff)
    _maybe_update(user, 'is_superuser', is_superuser)

    # Set unusable password if specified
    if unusable_password and user.has_usable_password():
        user.set_unusable_password()

    # Ensure the user has a profile
    try:
        __ = user.profile
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=user)

    # resolve the specified groups
    for group_name in groups or set():

        try:
            group = Group.objects.get(name=group_name)
            new_groups.add(group)
        except Group.DoesNotExist:
            pass

    add_groups = new_groups - old_groups
    remove_groups = old_groups - new_groups

    user.groups.set(new_groups)
    user.save()
    sys.stderr.write(_('Created new user: "{}"').format(user))