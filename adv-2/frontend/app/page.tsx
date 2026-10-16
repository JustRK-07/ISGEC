import { Nav } from "@/components/marketing/Nav";
import { Hero } from "@/components/marketing/Hero";
import { LocalModel } from "@/components/marketing/LocalModel";
import { ProblemCards } from "@/components/marketing/ProblemCards";
import { Pipeline } from "@/components/marketing/Pipeline";
import { Capabilities } from "@/components/marketing/Capabilities";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { WhyAgentic } from "@/components/marketing/WhyAgentic";
import { Defensibility } from "@/components/marketing/Defensibility";
import { SupportedFormats } from "@/components/marketing/SupportedFormats";
import { Integrations } from "@/components/marketing/Integrations";
import { Security } from "@/components/marketing/Security";
import { UseCases } from "@/components/marketing/UseCases";
import { Standards } from "@/components/marketing/Standards";
import { Testimonials } from "@/components/marketing/Testimonials";
import { FAQ } from "@/components/marketing/FAQ";
import { FinalCTA } from "@/components/marketing/FinalCTA";
import { Footer } from "@/components/marketing/Footer";
import { RevealInit } from "@/components/marketing/RevealInit";

export default function HomePage() {
  return (
    <>
      <RevealInit />
      <Nav />
      <main className="landing">
        <Hero />
        <LocalModel />
        <ProblemCards />
        <Pipeline />
        <Capabilities />
        <HowItWorks />
        <WhyAgentic />
        <Defensibility />
        <SupportedFormats />
        <Integrations />
        <Security />
        <UseCases />
        <Standards />
        <Testimonials />
        <FAQ />
        <FinalCTA />
        <Footer />
      </main>
    </>
  );
}
