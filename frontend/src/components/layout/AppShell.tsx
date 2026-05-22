/**
 * AppShell layout component for ClinNote AI
 *
 * Main application layout: sidebar + top bar + content area.
 * Includes HIPAA inactivity timer and warning modal.
 * Hosts global overlays: command palette, ICD reasoning drawer.
 */

import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { InactivityWarning } from '@/components/molecules/InactivityWarning';
import { useInactivityTimer } from '@/hooks/useInactivityTimer';
import { CommandPaletteHost } from '@/components/organisms/CommandPalette';
import { ICDReasoningDrawerHost } from '@/components/molecules/ICDReasoningDrawer';

/**
 * Root Application Shell
 */
export const AppShell: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { showWarning, secondsRemaining, dismissWarning } = useInactivityTimer();

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
      {/* Sidebar */}
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <TopBar onOpenSidebar={() => setSidebarOpen(true)} />

        {/* Page content */}
        <main
          id="main-content"
          className="flex-1 overflow-y-auto"
          role="main"
          aria-label="Main content"
        >
          <div className="p-4 tablet:p-6 max-w-7xl mx-auto w-full">
            <Outlet />
          </div>
        </main>
      </div>

      {/* HIPAA Inactivity Warning */}
      <InactivityWarning
        isOpen={showWarning}
        secondsRemaining={secondsRemaining}
        onDismiss={dismissWarning}
      />

      {/* Global overlays — mount once, controllable from anywhere */}
      <CommandPaletteHost />
      <ICDReasoningDrawerHost />
    </div>
  );
};
