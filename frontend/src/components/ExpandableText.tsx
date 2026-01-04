"use client";

import React, { useState } from 'react';

interface ExpandableTextProps {
    text: string;
    maxLength?: number;
    className?: string;
    style?: React.CSSProperties;
}

const ExpandableText: React.FC<ExpandableTextProps> = ({
    text,
    maxLength = 60,
    className = "",
    style = {}
}) => {
    const [expanded, setExpanded] = useState(false);

    if (!text) return null;

    // If text is shorter than limit, just show it
    if (text.length <= maxLength) {
        return <span className={className} style={style}>{text}</span>;
    }

    return (
        <span className={className} style={style}>
            {expanded ? text : `${text.slice(0, maxLength)}...`}

            <button
                onClick={(e) => {
                    e.stopPropagation();
                    setExpanded(!expanded);
                }}
                style={{
                    background: 'none',
                    border: 'none',
                    padding: '0 0 0 4px',
                    margin: 0,
                    cursor: 'pointer',
                    color: 'var(--color-primary)',
                    fontSize: 'inherit',
                    fontWeight: 500,
                    textDecoration: 'underline'
                }}
            >
                {expanded ? 'less' : 'more'}
            </button>
        </span>
    );
};

export default ExpandableText;
