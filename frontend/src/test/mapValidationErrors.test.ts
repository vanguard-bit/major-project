import { describe, it, expect } from 'vitest';
import { mapValidationErrorsToForm } from '../lib/mapValidationErrors';

describe('mapValidationErrorsToForm', () => {
  it('maps FastAPI 422 loc leaf to field name', () => {
    const err = {
      response: {
        data: {
          detail: [
            { loc: ['body', 'base_url'], msg: 'invalid url', type: 'value_error' },
            { loc: ['body', 'token_config', 'client_id'], msg: 'required', type: 'missing' },
          ],
        },
      },
    };
    expect(mapValidationErrorsToForm(err)).toEqual({
      base_url: 'invalid url',
      client_id: 'required',
    });
  });

  it('returns empty object when detail missing', () => {
    expect(mapValidationErrorsToForm({})).toEqual({});
  });
});
