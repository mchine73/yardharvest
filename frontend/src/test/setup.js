// Vitest global setup: extends expect with jest-dom matchers (toBeInTheDocument,
// toHaveClass, etc.) and clears the DOM between tests.
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Every component that calls useTranslation needs a real i18next instance, or
// react-i18next returns the key and each assertion on the copy fails. Doing it
// here rather than per test file has a second payoff: the English assertions
// already in the suite now check that the en catalog still says what the
// hardcoded string said, which is the half of a translation nobody reviews.
import i18n from '../i18n';

afterEach(async () => {
  cleanup();
  // A test that switched to Spanish must not leak it into the next file.
  if (i18n.language !== 'en') await i18n.changeLanguage('en');
});
