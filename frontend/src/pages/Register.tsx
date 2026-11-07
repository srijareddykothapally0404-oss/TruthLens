// ============================================================
// TruthLens - Register Page
// ============================================================

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Mail, Lock, User, Eye, EyeOff, AlertCircle, Loader2, CheckCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../lib/stores';
import { authApi } from '../lib/api';
import { Button, Input, Card, CardHeader, CardTitle, CardContent, CardFooter } from '../components/ui';

export function Register() {
  const navigate = useNavigate();
  const { login, setError } = useAuthStore();

  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    password: '',
    confirm_password: '',
    organization: '',
    role: 'analyst',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.first_name.trim()) {
      newErrors.first_name = 'First name is required';
    }

    if (!formData.last_name.trim()) {
      newErrors.last_name = 'Last name is required';
    }

    if (!formData.email.trim()) {
      newErrors.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Please enter a valid email address';
    } else if (!formData.email.endsWith('.gov') && !formData.email.endsWith('.mil')) {
      newErrors.email = 'Government email (.gov or .mil) required';
    }

    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 12) {
      newErrors.password = 'Password must be at least 12 characters';
    } else if (!/[A-Z]/.test(formData.password)) {
      newErrors.password = 'Password must contain at least one uppercase letter';
    } else if (!/[a-z]/.test(formData.password)) {
      newErrors.password = 'Password must contain at least one lowercase letter';
    } else if (!/[0-9]/.test(formData.password)) {
      newErrors.password = 'Password must contain at least one number';
    } else if (!/[^A-Za-z0-9]/.test(formData.password)) {
      newErrors.password = 'Password must contain at least one special character';
    }

    if (formData.password !== formData.confirm_password) {
      newErrors.confirm_password = 'Passwords do not match';
    }

    if (!formData.organization.trim()) {
      newErrors.organization = 'Organization/Agency is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setErrors({});

    if (!validateForm()) return;

    setIsSubmitting(true);

    try {
      const { user, tokens } = await authApi.register({
        ...formData,
        role: formData.role as 'analyst' | 'supervisor' | 'admin',
      });
      login(user, tokens);
      setSuccess(true);
      setTimeout(() => navigate('/'), 2000);
    } catch (error) {
      if (error instanceof Error && error.message.includes('email')) {
        setErrors({ email: error.message });
      } else {
        setError(error instanceof Error ? error.message : 'Registration failed. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: '' }));
    }
  };

  const passwordStrength = {
    score: 0,
    checks: [
      { label: 'At least 12 characters', test: formData.password.length >= 12 },
      { label: 'One uppercase letter', test: /[A-Z]/.test(formData.password) },
      { label: 'One lowercase letter', test: /[a-z]/.test(formData.password) },
      { label: 'One number', test: /[0-9]/.test(formData.password) },
      { label: 'One special character', test: /[^A-Za-z0-9]/.test(formData.password) },
    ],
  };

  passwordStrength.checks.forEach((check) => {
    if (check.test) passwordStrength.score++;
  });

  if (success) {
    return (
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="flex items-center justify-center w-14 h-14 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700">
              <Shield className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">TruthLens</h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">Government Platform</p>
            </div>
          </div>
        </div>

        <Card variant="elevated" padding="lg" className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
            <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-400" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">Registration Successful</h2>
          <p className="text-gray-600 dark:text-gray-400">Welcome to TruthLens. Redirecting to dashboard...</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md">
      {/* Brand Header */}
      <div className="text-center mb-8">
        <div className="flex items-center justify-center gap-3 mb-4">
          <div className="flex items-center justify-center w-14 h-14 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">TruthLens</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Government Platform</p>
          </div>
        </div>
        <p className="text-gray-600 dark:text-gray-400">Request access to the evidence verification workspace</p>
      </div>

      {/* Register Card */}
      <Card variant="elevated" padding="lg">
        <CardHeader>
          <CardTitle>Create your account</CardTitle>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            {useAuthStore.getState().error && (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <span>{useAuthStore.getState().error}</span>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <Input
                label="First Name"
                name="first_name"
                value={formData.first_name}
                onChange={handleChange}
                placeholder="John"
                required
                autoComplete="given-name"
                leftIcon={<User className="w-5 h-5" />}
                error={errors.first_name}
              />
              <Input
                label="Last Name"
                name="last_name"
                value={formData.last_name}
                onChange={handleChange}
                placeholder="Doe"
                required
                autoComplete="family-name"
                leftIcon={<User className="w-5 h-5" />}
                error={errors.last_name}
              />
            </div>

            <Input
              label="Email Address"
              name="email"
              type="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="analyst@agency.gov"
              required
              autoComplete="email"
              leftIcon={<Mail className="w-5 h-5" />}
              error={errors.email}
            />

            <Input
              label="Organization / Agency"
              name="organization"
              value={formData.organization}
              onChange={handleChange}
              placeholder="Department of Homeland Security"
              required
              autoComplete="organization"
              leftIcon={<User className="w-5 h-5" />}
              error={errors.organization}
            />

            <Select
              label="Role"
              name="role"
              value={formData.role}
              onChange={handleChange}
              options={[
                { value: 'analyst', label: 'Analyst' },
                { value: 'supervisor', label: 'Supervisor' },
              ]}
              placeholder="Select your role"
              leftIcon={<User className="w-5 h-5" />}
              error={errors.role}
            />

            <div className="relative">
              <Input
                label="Password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                value={formData.password}
                onChange={handleChange}
                placeholder="Create a strong password"
                required
                autoComplete="new-password"
                leftIcon={<Lock className="w-5 h-5" />}
                rightElement={
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                }
                error={errors.password}
              />
            </div>

            {formData.password && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-500 dark:text-gray-400">Password strength</span>
                  <span className={cn('font-medium', passwordStrength.score <= 2 && 'text-red-600', passwordStrength.score === 3 && 'text-yellow-600', passwordStrength.score >= 4 && 'text-green-600')}>
                    {['Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong'][passwordStrength.score - 1] || 'Very Weak'}
                  </span>
                </div>
                <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className="h-full transition-all duration-300"
                    style={{
                      width: `${(passwordStrength.score / 5) * 100}%`,
                      backgroundColor:
                        passwordStrength.score <= 2
                          ? '#ef4444'
                          : passwordStrength.score === 3
                          ? '#f59e0b'
                          : '#22c55e',
                    }}
                  />
                </div>
                <ul className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
                  {passwordStrength.checks.map((check, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <span className={cn('w-3 h-3 rounded-full', check.test ? 'bg-green-500' : 'bg-gray-300 dark:bg-gray-600')} />
                      <span className={cn(check.test ? 'text-green-600 dark:text-green-400' : '')}>{check.label}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="relative">
              <Input
                label="Confirm Password"
                name="confirm_password"
                type={showConfirmPassword ? 'text' : 'password'}
                value={formData.confirm_password}
                onChange={handleChange}
                placeholder="Confirm your password"
                required
                autoComplete="new-password"
                leftIcon={<Lock className="w-5 h-5" />}
                rightElement={
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                  >
                    {showConfirmPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                }
                error={errors.confirm_password}
              />
            </div>

            <div className="flex items-start gap-2">
              <input
                type="checkbox"
                id="terms"
                required
                className="mt-1 w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-2 focus:ring-blue-500"
              />
              <label htmlFor="terms" className="text-sm text-gray-600 dark:text-gray-400">
                I agree to the <Link to="/terms" className="text-blue-600 hover:text-blue-700 dark:text-blue-400">Terms of Service</Link> and
                <Link to="/privacy" className="text-blue-600 hover:text-blue-700 dark:text-blue-400 ml-1">Privacy Policy</Link>
              </label>
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              fullWidth
              loading={isSubmitting}
              leftIcon={!isSubmitting ? null : <Loader2 className="w-4 h-4" />}
            >
              {isSubmitting ? 'Creating account...' : 'Create Account'}
            </Button>
          </form>
        </CardContent>

        <CardFooter className="flex-col gap-4">
          <div className="relative w-full">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-200 dark:border-gray-700" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-400">Or</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Button variant="outline" type="button" leftIcon={<svg className="w-4 h-4" viewBox="0 0 24 24"><path fill="currentColor" d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/></svg>}>
              Google
            </Button>
            <Button variant="outline" type="button" leftIcon={<svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/></svg>}>
              GitHub
            </Button>
          </div>
        </CardFooter>
      </Card>

      {/* Footer */}
      <div className="mt-6 text-center text-sm text-gray-500 dark:text-gray-400">
        <p>Already have an account? <Link to="/login" className="text-blue-600 hover:text-blue-700 dark:text-blue-400 font-medium">Sign in</Link></p>
        <p className="mt-2">Government email (.gov/.mil) required for registration</p>
      </div>
    </div>
  );
}