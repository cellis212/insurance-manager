# Insurance Manager - Frontend

This is the Next.js 14 frontend for the Insurance Manager educational simulation game.

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn
- Backend API running at http://localhost:8000

### Environment Variables

Create a `.env.local` file in the frontend directory:

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### Installation

```bash
npm install
# or
yarn install
```

### Development

Run the development server:

```bash
npm run dev
# or
yarn dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser.

## Project Structure

- `/app` - Next.js 14 app directory with pages
- `/components` - Reusable React components
- `/lib` - Utility functions and API client
- `/stores` - Zustand state management stores
- `/hooks` - Custom React hooks

## Key Features

- JWT authentication with access/refresh tokens
- Multi-step company creation wizard
- Real-time dashboard with financial metrics
- Decision submission forms for each game system
- Responsive design with Tailwind CSS

## Authentication Flow

1. User registers or logs in at `/auth/login`
2. New users are redirected to `/company/create` 
3. After company creation, users access the main dashboard
4. JWT tokens are stored in localStorage via Zustand persist

## API Integration

All API calls use the `apiClient` in `/lib/api-client.ts` which:
- Automatically includes JWT authentication headers
- Handles errors consistently
- Works with TanStack Query for caching

## State Management

- Authentication state: `useAuthStore`
- Game state: `useGameStore` 
- Decision drafts: `useDecisionsStore`

All stores use Zustand with TypeScript for type safety.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
