# Authentication

How signing in and out works in AI-IOS today. Only documents what's
actually built — no registration or multi-factor sign-in flow exists
in this interface yet, even though the backend understands both.

## Signing in

Go to `/login`. Enter your email and password, then select **Sign
In**. AI-IOS remembers you're signed in across visits unless you sign
out or your session expires.

- Select the eye icon next to the password field to show or hide what
  you've typed.
- **Keep me signed in** is available on every login — it's passed to
  the backend on every sign-in attempt.
- If you open `/login` while already signed in, you're sent straight
  to where you were headed instead of seeing the form again.

## Session behaviour

Every page except `/login` requires you to be signed in. If you try to
open a page without a session, you're sent to `/login` and returned to
that same page once you sign in.

Your session doesn't last forever. If it expires while you're using
AI-IOS, you'll be returned to the sign-in page with a note that your
session expired — sign in again to continue where you left off.

## Signing out

Open the account menu (top right) and select **Sign out**. This ends
your session and returns you to the sign-in page. Once signed out, you
can't get back to a protected page by pressing the browser's back
button — you'll be sent to sign in again.

## Common authentication errors

| What you see | What it means |
| --- | --- |
| "Unable to sign in with those credentials." | The email or password is wrong. AI-IOS doesn't say which one, for your account's security. |
| "This account isn't allowed to sign in right now." | Contact your administrator. |
| "Too many sign-in attempts. Please wait a moment and try again." | Wait a bit before trying again. |
| "Something went wrong on our end. Please try again." | A temporary problem on the server. Try again shortly. |
| "Unable to connect to the authentication service. Please try again." | AI-IOS couldn't reach the server at all — check your connection. |
| "Your session has expired" (on the sign-in page) | You were signed in but your session timed out; sign in again. |

If your account requires multi-factor authentication, sign-in will
tell you this interface doesn't support entering a code yet — contact
your administrator (see Troubleshooting).

## Accessibility

The sign-in form works fully with a keyboard: `Tab`/`Shift+Tab` move
between fields, `Enter` submits, and the password show/hide button is
reachable and operable without a mouse. Every field has a real label,
not just placeholder text, and errors are announced to screen readers
as they appear.

## Troubleshooting

- **I can't remember if I'm signed in.** Just try opening AI-IOS — if
  you're not signed in, you'll land on `/login` automatically.
- **I keep getting sent back to the sign-in page.** Your session may
  be expiring quickly, or your browser may be blocking local storage
  (AI-IOS needs it to stay signed in). Check your browser's privacy
  settings.
- **Sign-in says I need multi-factor authentication.** This interface
  doesn't yet support entering a code — contact your administrator for
  next steps.
- **I still can't sign in after several tries.** Contact your
  administrator; they can check your account's status on their side.
