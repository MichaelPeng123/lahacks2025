"use client";
import { useEffect } from "react";
import { motion, stagger, useAnimate } from "motion/react";
import { cn } from "@/lib/utils";

export const TextGenerateEffect = ({
  words,
  className,
  filter = true,
  duration = 0.5,
}: {
  words: string;
  className?: string;
  filter?: boolean;
  duration?: number;
}) => {
  const [scope, animate] = useAnimate();
  let wordsArray = words.split(" ");
  
  useEffect(() => {
    animate(
      "span",
      {
        opacity: 1,
        filter: filter ? "blur(0px)" : "none",
      },
      {
        duration: duration ? duration : 1,
        delay: stagger(0.1), 
      }
    );
  }, [scope.current, animate, duration, filter]);

  const renderWords = () => {
    return (
      <motion.div ref={scope} className="whitespace-pre-wrap">
        {wordsArray.map((word, idx) => (
          <motion.span
            key={word + idx}
            className="opacity-0 inline-block"
            style={{
              filter: filter ? "blur(8px)" : "none",
            }}
          >
            {word}
            {idx < wordsArray.length - 1 ? " " : ""}
          </motion.span>
        ))}
      </motion.div>
    );
  };

  return (
    <div className={cn("text-black dark:text-white", className)}>
      <div className="leading-relaxed whitespace-normal">
        {renderWords()}
      </div>
    </div>
  );
};
