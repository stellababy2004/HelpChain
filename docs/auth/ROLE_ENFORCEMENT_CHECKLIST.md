# HelpChain — Role Enforcement Checklist

## Admin family
- [ ] Unauthenticated `/admin` redirects to `/admin/login`
- [ ] `/admin/login` renders correctly
- [ ] Admin success redirects by role
- [ ] Volunteer session cannot access admin pages
- [ ] Volunteer identifiers are not accepted by admin login logic

## Volunteer
- [ ] Unauthenticated volunteer page redirects to volunteer entry flow
- [ ] `/volunteer_login` or volunteer entry flow renders correctly
- [ ] Admin session does not become a volunteer session
- [ ] Admin identifiers are not accepted by volunteer flow

## Professional
- [ ] Professional access remains review-based
- [ ] No direct professional login route exists yet
- [ ] Approving a ProfessionalLead does not create unintended admin auth
- [ ] Intervenant remains operational unless explicit professional auth is introduced