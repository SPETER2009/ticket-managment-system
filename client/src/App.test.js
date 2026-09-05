import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { UserProvider } from './context/UserContext';
import App from './App';

test('renders sign in screen by default', () => {
  render(
    <BrowserRouter>
      <UserProvider>
        <App />
      </UserProvider>
    </BrowserRouter>
  );
  const signInElements = screen.getAllByText(/sign in/i);
  expect(signInElements.length).toBeGreaterThan(0);
});
