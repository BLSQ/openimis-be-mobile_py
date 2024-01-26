from django.test import TestCase
from django.core.exceptions import ValidationError

from mobile.models import Control


class ModelsTestCase(TestCase):
  DEFAULT_NAME = 'a_field'
  DEFAULT_ADJUSTABILITY = Control.Adjustability.OPTIONAL
  DEFAULT_USAGE = 'a_form'

  def test_basic_creation(self):
    control = Control.objects.create(
      name=ModelsTestCase.DEFAULT_NAME,
      adjustability=ModelsTestCase.DEFAULT_ADJUSTABILITY,
      usage=ModelsTestCase.DEFAULT_USAGE)

    self.assertEqual(control.name, 'a_field')
    self.assertEqual(control.adjustability, Control.Adjustability.OPTIONAL)
    self.assertEqual(control.usage, 'a_form')
    self.assertEqual(str(control), 'Field a_field (Optional) for forms a_form')

  def test_unvalid_adjustability(self):
    unvalid_adjustability_values = [
      'H',
      'Hidden',
      'None',
      'F',
    ]
    for unvalid_value in unvalid_adjustability_values:
      control = Control.objects.create(
        name = f'{ModelsTestCase.DEFAULT_NAME}_{unvalid_value}',
        adjustability = unvalid_value,
        usage = ModelsTestCase.DEFAULT_USAGE)
      with self.assertRaises(ValidationError) as context:
        control.clean_fields()

    valid_adjustability_values = [
      'O',
      'N',
      'M',
      'R'
    ]
    for valid_value in valid_adjustability_values:
      control = Control.objects.create(
        name = f'{ModelsTestCase.DEFAULT_NAME}_{valid_value}',
        adjustability = valid_value,
        usage = ModelsTestCase.DEFAULT_USAGE)
      try:
        control.clean_fields()
      except ValidationError:
        self.fail(f'A ValidationError has been raised for value {valid_value} when it shouldn\'t' )

